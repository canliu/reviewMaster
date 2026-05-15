"""Repeat-orders queries.

All three queries (summary, list, detail) build off the same `repeat_groups`
CTE: the rows of `buyer_product_stats` for this user, shop, and grain where
`order_count >= min_purchases`. From there:

  * `summary` rolls them up.
  * `list_orders` joins back to `orders` with `ROW_NUMBER()` for
    `purchase_index`, layers the filter set on top, paginates.
  * `detail` is the same join for one `order_uuid` plus a buyer_history slice.

Raw SQL via SQLAlchemy text() is used because the CTE + window function +
review-request join is awkward in the ORM and the queries are hot paths.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models.user import User
from app.models.user_settings import UserSettings

VALID_GRAINS = {"asin", "spu", "product_name"}
VALID_SORTS = {"last_order_desc", "purchase_count_desc", "delivery_asc"}
DEFAULT_MIN_PURCHASES = 2

WINDOW_MIN = timedelta(days=5)
WINDOW_MAX = timedelta(days=30)


# ---------- helpers ----------

def _grain_column(grain: str) -> str:
    """The orders column matching the chosen grain."""
    return {"asin": "asin", "spu": "spu", "product_name": "product_name"}[grain]


# Virtual shop_site prefix that means "all of this user's shops in a given
# marketplace" — e.g. `all:US` covers `p3:US` and `p4:US`.
ALL_SCOPE_PREFIX = "all:"


def _marketplace_of(shop_site: str) -> str | None:
    """Return the marketplace token (after the rightmost `:`). `p3:US` → `US`."""
    if not shop_site or ":" not in shop_site:
        return None
    return shop_site.rsplit(":", 1)[1].strip().upper() or None


async def _resolve_shop_scope(
    db: AsyncSession, user_id, scope: str
) -> list[str]:
    """Expand a scope string into a list of real shop_site values.

    A real shop (`p3:US`) returns `["p3:US"]`. The virtual `all:US` returns
    every shop_site the user has uploaded that's in the US marketplace.
    """
    from app.models.order import Order
    from sqlalchemy import select

    if scope.startswith(ALL_SCOPE_PREFIX):
        market = scope[len(ALL_SCOPE_PREFIX):].strip().upper()
        rows = (
            await db.execute(
                select(Order.shop_site)
                .where(Order.user_id == user_id)
                .where(Order.shop_site.is_not(None))
                .distinct()
            )
        ).all()
        return sorted(
            {r[0] for r in rows if _marketplace_of(r[0]) == market}
        )
    return [scope]


async def _load_settings(db: AsyncSession, user: User) -> UserSettings:
    row = await db.get(UserSettings, user.id)
    if row is None:
        # Defaults — shouldn't happen because register creates the row, but
        # safer than crashing.
        row = UserSettings(user_id=user.id)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _can_request(estimated_delivery: datetime | None, active_review: bool) -> tuple[bool, str | None]:
    if active_review:
        return False, "already requested"
    if estimated_delivery is None:
        return False, "missing delivery date"
    age = _now_utc() - estimated_delivery
    if age < WINDOW_MIN:
        return False, "too early (< 5 days after delivery)"
    if age >= WINDOW_MAX:
        return False, "too late (> 30 days after delivery)"
    return True, None


def _truncate(value: str | None, max_len: int = 80) -> str | None:
    if value is None:
        return None
    if len(value) <= max_len:
        return value
    return value[: max_len - 1] + "…"


# ---------- summary ----------

async def summary(db: AsyncSession, user: User) -> dict[str, int]:
    settings = await _load_settings(db, user)
    if settings.active_shop_site is None:
        return {
            "total_repeat_orders": 0,
            "total_repeat_buyers": 0,
            "total_repeat_products": 0,
            "in_review_window": 0,
            "already_requested": 0,
        }

    grain = settings.repeat_grain
    grain_col = _grain_column(grain)
    excluded = list(settings.excluded_order_types or [])
    now = _now_utc()
    earliest_in_window = now - WINDOW_MAX
    latest_in_window = now - WINDOW_MIN

    shops = await _resolve_shop_scope(db, user.id, settings.active_shop_site)
    if not shops:
        return {
            "total_repeat_orders": 0,
            "total_repeat_buyers": 0,
            "total_repeat_products": 0,
            "in_review_window": 0,
            "already_requested": 0,
        }

    # repeat_groups SUMs across the resolved shops so cross-shop repeats
    # within the same marketplace are counted as one repeat group.
    sql = text(
        f"""
        WITH repeat_groups AS (
            SELECT buyer_key, group_value, SUM(order_count) AS order_count
            FROM buyer_product_stats
            WHERE user_id = :uid
              AND shop_site = ANY(CAST(:shops AS text[]))
              AND grain = :grain
            GROUP BY buyer_key, group_value
            HAVING SUM(order_count) >= :min_purchases
        ),
        relevant AS (
            SELECT o.id, o.buyer_key, o.{grain_col} AS group_value,
                   o.estimated_delivery_utc
            FROM orders o
            INNER JOIN repeat_groups rg
              ON rg.buyer_key = o.buyer_key
             AND rg.group_value = o.{grain_col}
            WHERE o.user_id = :uid
              AND o.shop_site = ANY(CAST(:shops AS text[]))
              AND (cardinality(CAST(:excluded AS text[])) = 0
                   OR o.order_type IS NULL
                   OR NOT (o.order_type = ANY(CAST(:excluded AS text[]))))
        )
        SELECT
            (SELECT COUNT(*) FROM relevant) AS total_repeat_orders,
            (SELECT COUNT(DISTINCT buyer_key) FROM relevant) AS total_repeat_buyers,
            (SELECT COUNT(DISTINCT (buyer_key, group_value)) FROM relevant)
              AS total_repeat_products,
            (SELECT COUNT(*) FROM relevant r
              WHERE r.estimated_delivery_utc IS NOT NULL
                AND r.estimated_delivery_utc >= :earliest_in_window
                AND r.estimated_delivery_utc <= :latest_in_window
                AND NOT EXISTS (
                  SELECT 1 FROM review_requests rr
                  WHERE rr.user_id = :uid
                    AND rr.order_uuid = r.id
                    AND rr.status IN ('sent', 'pending')
                )
            ) AS in_review_window,
            (SELECT COUNT(*) FROM relevant r
              WHERE EXISTS (
                SELECT 1 FROM review_requests rr
                WHERE rr.user_id = :uid
                  AND rr.order_uuid = r.id
                  AND rr.status IN ('sent', 'pending')
              )
            ) AS already_requested
        """
    ).bindparams(bindparam("excluded", expanding=False))

    row = (
        await db.execute(
            sql,
            {
                "uid": user.id,
                "shops": shops,
                "grain": grain,
                "min_purchases": DEFAULT_MIN_PURCHASES,
                "excluded": excluded,
                "earliest_in_window": earliest_in_window,
                "latest_in_window": latest_in_window,
            },
        )
    ).one()

    return {
        "total_repeat_orders": int(row.total_repeat_orders or 0),
        "total_repeat_buyers": int(row.total_repeat_buyers or 0),
        "total_repeat_products": int(row.total_repeat_products or 0),
        "in_review_window": int(row.in_review_window or 0),
        "already_requested": int(row.already_requested or 0),
    }


# ---------- list ----------

VALID_REQUEST_STATUSES = {"none", "pending", "sent", "failed"}


async def list_orders(
    db: AsyncSession,
    user: User,
    *,
    page: int = 1,
    page_size: int = 50,
    asin: str | None = None,
    product_search: str | None = None,
    has_review_request: bool | None = None,
    request_status: str | None = None,
    in_window: bool | None = None,
    min_purchases: int = DEFAULT_MIN_PURCHASES,
    sort: str = "last_order_desc",
    shop_site_override: str | None = None,
    shop_filter: str | None = None,
) -> dict[str, Any]:
    """List repeat orders.

    ``shop_site_override`` lets the caller (typically the CSV export)
    pick a shop that isn't the active one. ``request_status`` is a
    fine-grained filter — when set it overrides ``has_review_request`` and
    accepts the literal strings ``none|pending|sent|failed``.
    """
    if sort not in VALID_SORTS:
        raise APIError(422, "INVALID_SORT", f"sort must be one of {sorted(VALID_SORTS)}.")
    if page < 1 or page_size < 1 or page_size > 200:
        raise APIError(422, "INVALID_PAGINATION", "page>=1, 1<=page_size<=200.")
    if request_status is not None and request_status not in VALID_REQUEST_STATUSES:
        raise APIError(
            422,
            "INVALID_REQUEST_STATUS",
            f"request_status must be one of {sorted(VALID_REQUEST_STATUSES)}.",
        )

    settings = await _load_settings(db, user)
    empty = {"total": 0, "page": page, "page_size": page_size, "items": []}
    scope = (shop_site_override or settings.active_shop_site or "").strip()
    if not scope:
        return empty
    shops = await _resolve_shop_scope(db, user.id, scope)
    if not shops:
        return empty

    grain = settings.repeat_grain
    grain_col = _grain_column(grain)
    excluded = list(settings.excluded_order_types or [])

    order_by_sql = {
        "last_order_desc": "order_time_utc DESC NULLS LAST, id DESC",
        "purchase_count_desc": "total_purchases DESC, order_time_utc DESC NULLS LAST, id DESC",
        "delivery_asc": "estimated_delivery_utc ASC NULLS LAST, id ASC",
    }[sort]

    # repeat_groups SUMs counts across the resolved shop list, so cross-shop
    # repeats within the same marketplace are detected.
    base_cte = f"""
        WITH repeat_groups AS (
            SELECT buyer_key, group_value, SUM(order_count) AS order_count
            FROM buyer_product_stats
            WHERE user_id = :uid
              AND shop_site = ANY(CAST(:shops AS text[]))
              AND grain = :grain
            GROUP BY buyer_key, group_value
            HAVING SUM(order_count) >= :min_purchases
        ),
        ordered AS (
            SELECT o.id, o.user_id, o.order_id, o.shop_site, o.asin, o.spu,
                   o.product_name, o.product_title, o.order_type,
                   o.buyer_email, o.buyer_key,
                   o.order_time_utc, o.estimated_delivery_utc,
                   o.item_price, o.currency, o.quantity,
                   o.ship_city, o.ship_state, o.ship_country,
                   rg.order_count AS total_purchases,
                   ROW_NUMBER() OVER (
                     PARTITION BY o.buyer_key, o.{grain_col}
                     ORDER BY o.order_time_utc NULLS LAST, o.id
                   ) AS purchase_index,
                   EXISTS (
                     SELECT 1 FROM review_requests rr
                     WHERE rr.user_id = o.user_id AND rr.order_uuid = o.id
                   ) AS any_review_exists,
                   (
                     SELECT jsonb_build_object(
                       'id', rr.id,
                       'status', rr.status,
                       'method', rr.method,
                       'requested_at', rr.requested_at
                     )
                     FROM review_requests rr
                     WHERE rr.user_id = o.user_id
                       AND rr.order_uuid = o.id
                       AND rr.status IN ('sent', 'pending')
                     LIMIT 1
                   ) AS active_review
            FROM orders o
            INNER JOIN repeat_groups rg
              ON rg.buyer_key = o.buyer_key
             AND rg.group_value = o.{grain_col}
            WHERE o.user_id = :uid
              AND o.shop_site = ANY(CAST(:shops AS text[]))
              AND (cardinality(CAST(:excluded AS text[])) = 0
                   OR o.order_type IS NULL
                   OR NOT (o.order_type = ANY(CAST(:excluded AS text[]))))
        ),
        filtered AS (
            SELECT * FROM ordered
            WHERE (CAST(:asin AS text) IS NULL OR asin = :asin)
              AND (CAST(:product_search AS text) IS NULL
                   OR product_name ILIKE :search_like
                   OR product_title ILIKE :search_like)
              -- shop_filter narrows the result rows to one specific shop
              -- WITHOUT changing which orders count as repeats (the scope
              -- already determined that). Useful when scope = all:US and the
              -- user wants to focus on one shop's slice of the cross-shop pool.
              AND (CAST(:shop_filter AS text) IS NULL OR shop_site = :shop_filter)
              AND (
                CAST(:has_review_request AS boolean) IS NULL
                OR (CAST(:has_review_request AS boolean) = TRUE AND any_review_exists)
                OR (CAST(:has_review_request AS boolean) = FALSE AND NOT any_review_exists)
              )
              -- request_status: fine-grained — none means "no request row at all",
              -- pending/sent/failed match the active_review's status when set.
              AND (
                CAST(:request_status AS text) IS NULL
                OR (CAST(:request_status AS text) = 'none' AND NOT any_review_exists)
                OR (CAST(:request_status AS text) IN ('pending', 'sent')
                    AND active_review IS NOT NULL
                    AND active_review->>'status' = CAST(:request_status AS text))
                OR (CAST(:request_status AS text) = 'failed'
                    AND any_review_exists AND active_review IS NULL)
              )
              AND (
                CAST(:in_window AS boolean) IS NULL
                OR (CAST(:in_window AS boolean) = TRUE
                    AND estimated_delivery_utc IS NOT NULL
                    AND estimated_delivery_utc >= :earliest_in_window
                    AND estimated_delivery_utc <= :latest_in_window)
                OR (CAST(:in_window AS boolean) = FALSE
                    AND (estimated_delivery_utc IS NULL
                         OR estimated_delivery_utc < :earliest_in_window
                         OR estimated_delivery_utc > :latest_in_window))
              )
        )
    """

    count_sql = text(base_cte + " SELECT COUNT(*) FROM filtered")
    rows_sql = text(
        base_cte
        + f"""
        SELECT * FROM filtered
        ORDER BY {order_by_sql}
        LIMIT :limit OFFSET :offset
        """
    )

    now = _now_utc()
    params = {
        "uid": user.id,
        "shops": shops,
        "grain": grain,
        "min_purchases": int(min_purchases),
        "excluded": excluded,
        "asin": asin,
        "product_search": product_search,
        "search_like": f"%{product_search}%" if product_search else None,
        "has_review_request": has_review_request,
        "request_status": request_status,
        "shop_filter": shop_filter,
        "in_window": in_window,
        "earliest_in_window": now - WINDOW_MAX,
        "latest_in_window": now - WINDOW_MIN,
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }
    total = (await db.execute(count_sql, params)).scalar_one()
    raw_rows = (await db.execute(rows_sql, params)).mappings().all()
    items = [_serialize_item(row) for row in raw_rows]
    return {"total": int(total or 0), "page": page, "page_size": page_size, "items": items}


def _serialize_item(row: dict[str, Any]) -> dict[str, Any]:
    active = row.get("active_review")
    active_review_dict = active if isinstance(active, dict) else None
    estimated = row.get("estimated_delivery_utc")
    can_request, reason = _can_request(estimated, bool(active_review_dict))
    return {
        "order_uuid": row["id"],
        "order_id": row["order_id"],
        "shop_site": row["shop_site"],
        "asin": row.get("asin"),
        "spu": row.get("spu"),
        "product_name": row.get("product_name"),
        "product_title_short": _truncate(row.get("product_title"), 80),
        "order_type": row.get("order_type"),
        "buyer_email": row.get("buyer_email"),
        "buyer_key": row["buyer_key"],
        "order_time_utc": row.get("order_time_utc"),
        "estimated_delivery_utc": estimated,
        "item_price": float(row["item_price"]) if row.get("item_price") is not None else None,
        "currency": row.get("currency"),
        "quantity": row.get("quantity"),
        "ship_city": row.get("ship_city"),
        "ship_state": row.get("ship_state"),
        "ship_country": row.get("ship_country"),
        "purchase_index": int(row["purchase_index"]),
        "total_purchases": int(row["total_purchases"]),
        "review_request": (
            {
                "id": str(active_review_dict["id"]),
                "status": active_review_dict["status"],
                "method": active_review_dict["method"],
                "requested_at": active_review_dict["requested_at"],
            }
            if active_review_dict
            else None
        ),
        "can_request_review": can_request,
        "can_request_reason": reason,
    }


# ---------- detail ----------

async def detail(db: AsyncSession, user: User, order_uuid: UUID) -> dict[str, Any] | None:
    settings = await _load_settings(db, user)
    if settings.active_shop_site is None:
        return None

    shops = await _resolve_shop_scope(db, user.id, settings.active_shop_site)
    if not shops:
        return None

    grain = settings.repeat_grain
    grain_col = _grain_column(grain)
    excluded = list(settings.excluded_order_types or [])

    # Reuse the same CTE shape, but filter to one order_uuid (no pagination).
    # purchase_index counts across the scope's shops, so cross-shop repeats
    # share a single sequence.
    sql = text(
        f"""
        WITH repeat_groups AS (
            SELECT buyer_key, group_value, SUM(order_count) AS order_count
            FROM buyer_product_stats
            WHERE user_id = :uid
              AND shop_site = ANY(CAST(:shops AS text[]))
              AND grain = :grain
            GROUP BY buyer_key, group_value
            HAVING SUM(order_count) >= :min_purchases
        )
        SELECT o.id, o.user_id, o.order_id, o.shop_site, o.asin, o.spu,
               o.product_name, o.product_title, o.order_type,
               o.buyer_email, o.buyer_key,
               o.order_time_utc, o.estimated_delivery_utc,
               o.item_price, o.currency, o.quantity,
               o.ship_city, o.ship_state, o.ship_country,
               rg.order_count AS total_purchases,
               (
                 SELECT COUNT(*) FROM orders o2
                 WHERE o2.user_id = o.user_id
                   AND o2.shop_site = ANY(CAST(:shops AS text[]))
                   AND o2.buyer_key = o.buyer_key
                   AND o2.{grain_col} = o.{grain_col}
                   AND COALESCE(o2.order_time_utc, '-infinity') <
                       COALESCE(o.order_time_utc, '-infinity')
               ) + 1 AS purchase_index,
               EXISTS (
                 SELECT 1 FROM review_requests rr
                 WHERE rr.user_id = o.user_id AND rr.order_uuid = o.id
               ) AS any_review_exists,
               (
                 SELECT jsonb_build_object(
                   'id', rr.id,
                   'status', rr.status,
                   'method', rr.method,
                   'requested_at', rr.requested_at
                 )
                 FROM review_requests rr
                 WHERE rr.user_id = o.user_id
                   AND rr.order_uuid = o.id
                   AND rr.status IN ('sent', 'pending')
                 LIMIT 1
               ) AS active_review
        FROM orders o
        INNER JOIN repeat_groups rg
          ON rg.buyer_key = o.buyer_key
         AND rg.group_value = o.{grain_col}
        WHERE o.id = :order_uuid
          AND o.user_id = :uid
          AND o.shop_site = ANY(CAST(:shops AS text[]))
          AND (cardinality(CAST(:excluded AS text[])) = 0
               OR o.order_type IS NULL
               OR NOT (o.order_type = ANY(CAST(:excluded AS text[]))))
        """
    )
    row = (
        await db.execute(
            sql,
            {
                "uid": user.id,
                "shops": shops,
                "grain": grain,
                "min_purchases": DEFAULT_MIN_PURCHASES,
                "excluded": excluded,
                "order_uuid": order_uuid,
            },
        )
    ).mappings().first()
    if row is None:
        return None

    item = _serialize_item(row)

    # Buyer history — cross-product, this shop, newest first, capped at 50.
    history_cap = 50
    history_rows = (
        await db.execute(
            text(
                """
                SELECT o.order_id, o.asin, o.product_name, o.order_time_utc,
                       o.item_price, o.quantity,
                       (
                         SELECT rr.status FROM review_requests rr
                         WHERE rr.user_id = o.user_id
                           AND rr.order_uuid = o.id
                           AND rr.status IN ('sent', 'pending')
                         LIMIT 1
                       ) AS review_request_status
                FROM orders o
                WHERE o.user_id = :uid
                  AND o.shop_site = ANY(CAST(:shops AS text[]))
                  AND o.buyer_key = :buyer_key
                ORDER BY o.order_time_utc DESC NULLS LAST, o.id DESC
                LIMIT :cap
                """
            ),
            {
                "uid": user.id,
                "shops": shops,
                "buyer_key": item["buyer_key"],
                "cap": history_cap + 1,
            },
        )
    ).mappings().all()
    has_more = len(history_rows) > history_cap
    history_rows = history_rows[:history_cap]

    total_orders = (
        await db.execute(
            text(
                "SELECT COUNT(*) FROM orders WHERE user_id = :uid "
                "AND shop_site = ANY(CAST(:shops AS text[])) "
                "AND buyer_key = :buyer_key"
            ),
            {
                "uid": user.id,
                "shops": shops,
                "buyer_key": item["buyer_key"],
            },
        )
    ).scalar_one()

    return {
        "order": item,
        "buyer_history": {
            "buyer_key": item["buyer_key"],
            "buyer_email": item.get("buyer_email"),
            "total_orders_all_products": int(total_orders or 0),
            "orders_returned": len(history_rows),
            "has_more": has_more,
            "orders": [
                {
                    "order_id": r["order_id"],
                    "asin": r.get("asin"),
                    "product_name": r.get("product_name"),
                    "order_time_utc": r.get("order_time_utc"),
                    "item_price": float(r["item_price"]) if r.get("item_price") is not None else None,
                    "quantity": r.get("quantity"),
                    "review_request_status": r.get("review_request_status"),
                }
                for r in history_rows
            ],
        },
    }
