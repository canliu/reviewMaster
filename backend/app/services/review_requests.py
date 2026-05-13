"""Review-request creation, confirmation, and listing.

The non-obvious behavior is the **failed-retry pattern**: ``review_requests``
has UNIQUE(user_id, order_uuid) (only one row per order). To preserve audit
history when a previously-failed request is retried, we:

  1. Append a `system` note to ``review_request_notes`` summarizing the
     failure ("Superseded retry: previous attempt failed …").
  2. DELETE the old ``review_request`` row.
  3. INSERT the new row.

Steps 1–3 run in one transaction. Because notes are tied to the **order**,
not to the ``review_request``, the failure log persists through this
delete-and-reinsert. See stage_5_request.md for the schema rationale.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models.buyer_product_stat import BuyerProductStat
from app.models.order import Order
from app.models.review_request import ReviewRequest
from app.models.review_request_note import ReviewRequestNote
from app.models.user import User
from app.models.user_settings import UserSettings
from app.services.seller_central import build_seller_central_url

WINDOW_MIN = timedelta(days=5)
WINDOW_MAX = timedelta(days=30)


# ---------- helpers ----------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _grain_column_for_order(order: Order, grain: str) -> str | None:
    return {"asin": order.asin, "spu": order.spu, "product_name": order.product_name}[grain]


def _check_window(estimated: datetime | None) -> str | None:
    if estimated is None:
        return "missing delivery date"
    age = _now() - estimated
    if age < WINDOW_MIN:
        days = age.total_seconds() / 86400
        return f"too early ({days:.1f} days after delivery)"
    if age >= WINDOW_MAX:
        days = age.total_seconds() / 86400
        return f"too late ({days:.1f} days after delivery)"
    return None


# ---------- create ----------

async def create_requests(
    db: AsyncSession,
    user: User,
    order_uuids: list[UUID],
    method: str,
    note: str | None,
) -> dict[str, list[dict[str, Any]]]:
    """Bulk create review_requests. Validates per order; commits successes
    even when other orders fail validation."""

    if method not in {"manual", "link"}:
        raise APIError(422, "INVALID_METHOD", "method must be 'manual' or 'link'.")

    settings_row = await db.get(UserSettings, user.id)
    if settings_row is None or settings_row.active_shop_site is None:
        raise APIError(422, "NO_ACTIVE_SHOP", "Set an active shop first.")
    grain = settings_row.repeat_grain

    # Load all candidate orders once.
    orders = (
        (
            await db.execute(
                select(Order)
                .where(Order.user_id == user.id)
                .where(Order.id.in_(order_uuids))
            )
        )
        .scalars()
        .all()
    )
    found_by_id = {o.id: o for o in orders}

    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    # 1. ownership pre-check (each missing uuid → 403)
    missing_ids = [u for u in order_uuids if u not in found_by_id]
    if missing_ids:
        raise APIError(
            403,
            "FORBIDDEN",
            f"{len(missing_ids)} order(s) do not belong to you.",
        )

    # Collect stats keys we need to check repeat-status against.
    stat_lookup = await _build_repeat_lookup(db, user.id, orders, grain)

    for order in orders:
        # 2. repeat status
        group_value = _grain_column_for_order(order, grain)
        if not group_value or (order.shop_site, order.buyer_key, group_value) not in stat_lookup:
            errors.append(
                {
                    "order_uuid": order.id,
                    "code": "NOT_A_REPEAT_ORDER",
                    "reason": "not a repeat under the current grain/shop.",
                }
            )
            continue

        # 3. window
        reason = _check_window(order.estimated_delivery_utc)
        if reason is not None:
            errors.append(
                {
                    "order_uuid": order.id,
                    "code": "OUT_OF_WINDOW",
                    "reason": reason,
                }
            )
            continue

        # 4. active request check
        existing = (
            await db.execute(
                select(ReviewRequest)
                .where(ReviewRequest.user_id == user.id)
                .where(ReviewRequest.order_uuid == order.id)
            )
        ).scalar_one_or_none()

        if existing and existing.status in ("sent", "pending"):
            skipped.append({"order_uuid": order.id, "reason": "already requested"})
            continue

        if existing and existing.status == "failed":
            # Failed-retry: see module docstring.
            db.add(
                ReviewRequestNote(
                    user_id=user.id,
                    order_uuid=order.id,
                    review_request_id=existing.id,
                    note=(
                        f"Superseded retry: previous attempt ({existing.method}) "
                        f"failed at {existing.requested_at.isoformat()}"
                    ),
                    kind="system",
                )
            )
            await db.delete(existing)
            await db.flush()

        redirect_url: str | None = None
        if method == "link":
            try:
                redirect_url = build_seller_central_url(order.shop_site, order.order_id)
            except APIError as exc:
                errors.append(
                    {
                        "order_uuid": order.id,
                        "code": exc.code,
                        "reason": exc.message,
                    }
                )
                continue

        status = "sent" if method == "manual" else "pending"
        api_response = {"redirect_url": redirect_url} if redirect_url else None
        new_request = ReviewRequest(
            user_id=user.id,
            order_uuid=order.id,
            method=method,
            status=status,
            api_response=api_response,
        )
        db.add(new_request)
        await db.flush()
        if note:
            db.add(
                ReviewRequestNote(
                    user_id=user.id,
                    order_uuid=order.id,
                    review_request_id=new_request.id,
                    note=note,
                    kind="user",
                )
            )
        created.append(
            {
                "id": new_request.id,
                "order_uuid": order.id,
                "method": method,
                "status": status,
                "redirect_url": redirect_url,
            }
        )

    await db.commit()
    return {"created": created, "skipped": skipped, "errors": errors}


async def _build_repeat_lookup(
    db: AsyncSession, user_id: UUID, orders: Iterable[Order], grain: str
) -> set[tuple[str, str, str]]:
    """Return the set of (shop_site, buyer_key, group_value) tuples among
    these orders that are repeat groups (order_count >= 2)."""
    triples = set()
    for o in orders:
        gv = {"asin": o.asin, "spu": o.spu, "product_name": o.product_name}[grain]
        if gv:
            triples.add((o.shop_site, o.buyer_key, gv))
    if not triples:
        return set()
    shops = {t[0] for t in triples}
    buyers = {t[1] for t in triples}
    group_values = {t[2] for t in triples}

    rows = (
        await db.execute(
            select(
                BuyerProductStat.shop_site,
                BuyerProductStat.buyer_key,
                BuyerProductStat.group_value,
            )
            .where(BuyerProductStat.user_id == user_id)
            .where(BuyerProductStat.grain == grain)
            .where(BuyerProductStat.order_count >= 2)
            .where(BuyerProductStat.shop_site.in_(shops))
            .where(BuyerProductStat.buyer_key.in_(buyers))
            .where(BuyerProductStat.group_value.in_(group_values))
        )
    ).all()
    return {(r[0], r[1], r[2]) for r in rows}


# ---------- confirm ----------

async def confirm(
    db: AsyncSession, user: User, request_id: UUID
) -> ReviewRequest:
    req = await _load_owned(db, user, request_id)
    if req.status != "pending":
        raise APIError(
            422,
            "NOT_PENDING",
            f"Cannot confirm request in status '{req.status}'.",
        )
    req.status = "sent"
    await db.commit()
    await db.refresh(req)
    return req


async def confirm_as_manual(
    db: AsyncSession, user: User, request_id: UUID
) -> ReviewRequest:
    req = await _load_owned(db, user, request_id)
    if req.status != "pending":
        raise APIError(
            422,
            "NOT_PENDING",
            f"Cannot convert request in status '{req.status}'.",
        )
    req.status = "sent"
    req.method = "manual"
    await db.commit()
    await db.refresh(req)
    return req


async def _load_owned(
    db: AsyncSession, user: User, request_id: UUID
) -> ReviewRequest:
    req = (
        await db.execute(
            select(ReviewRequest)
            .where(ReviewRequest.id == request_id)
            .where(ReviewRequest.user_id == user.id)
        )
    ).scalar_one_or_none()
    if req is None:
        raise APIError(404, "NOT_FOUND", "Review request not found.")
    return req


# ---------- list ----------

async def list_requests(
    db: AsyncSession,
    user: User,
    *,
    page: int = 1,
    page_size: int = 50,
    method: str | None = None,
    status: str | None = None,
    shop_site: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> dict[str, Any]:
    if page < 1 or page_size < 1 or page_size > 200:
        raise APIError(422, "INVALID_PAGINATION", "page>=1, 1<=page_size<=200.")

    # Compute total + ids with a single query that joins the Order for shop filter.
    base = (
        select(ReviewRequest, Order)
        .join(Order, Order.id == ReviewRequest.order_uuid)
        .where(ReviewRequest.user_id == user.id)
    )
    if method is not None:
        base = base.where(ReviewRequest.method == method)
    if status is not None:
        base = base.where(ReviewRequest.status == status)
    if shop_site is not None:
        base = base.where(Order.shop_site == shop_site)
    if from_date is not None:
        base = base.where(ReviewRequest.requested_at >= from_date)
    if to_date is not None:
        base = base.where(ReviewRequest.requested_at <= to_date)

    # Total count.
    total = (
        await db.execute(
            select(func.count()).select_from(base.subquery())
        )
    ).scalar_one()

    rows = (
        await db.execute(
            base.order_by(ReviewRequest.requested_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    # Pre-load notes counts in one query.
    order_uuids = [o.id for _r, o in rows]
    counts = await _notes_counts(db, user.id, order_uuids)

    items = []
    for req, order in rows:
        items.append(
            {
                "id": req.id,
                "order_uuid": order.id,
                "method": req.method,
                "status": req.status,
                "requested_at": req.requested_at,
                "api_response": req.api_response,
                "order_id": order.order_id,
                "shop_site": order.shop_site,
                "asin": order.asin,
                "product_name": order.product_name,
                "buyer_email": order.buyer_email,
                "notes_count": counts.get(order.id, 0),
            }
        )

    return {"items": items, "total": int(total or 0), "page": page, "page_size": page_size}


async def _notes_counts(
    db: AsyncSession, user_id: UUID, order_uuids: list[UUID]
) -> dict[UUID, int]:
    if not order_uuids:
        return {}
    rows = (
        await db.execute(
            select(
                ReviewRequestNote.order_uuid,
                func.count(ReviewRequestNote.id),
            )
            .where(ReviewRequestNote.user_id == user_id)
            .where(ReviewRequestNote.order_uuid.in_(order_uuids))
            .group_by(ReviewRequestNote.order_uuid)
        )
    ).all()
    return {row[0]: int(row[1]) for row in rows}


# ---------- detail ----------

async def detail(
    db: AsyncSession, user: User, request_id: UUID
) -> dict[str, Any] | None:
    row = (
        await db.execute(
            select(ReviewRequest, Order)
            .join(Order, Order.id == ReviewRequest.order_uuid)
            .where(ReviewRequest.id == request_id)
            .where(ReviewRequest.user_id == user.id)
        )
    ).first()
    if row is None:
        return None
    req, order = row

    notes = (
        (
            await db.execute(
                select(ReviewRequestNote)
                .where(ReviewRequestNote.user_id == user.id)
                .where(ReviewRequestNote.order_uuid == order.id)
                .order_by(ReviewRequestNote.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    return {
        "request": {
            "id": req.id,
            "order_uuid": order.id,
            "method": req.method,
            "status": req.status,
            "requested_at": req.requested_at,
            "api_response": req.api_response,
            "order_id": order.order_id,
            "shop_site": order.shop_site,
            "asin": order.asin,
            "product_name": order.product_name,
            "buyer_email": order.buyer_email,
            "notes_count": len(notes),
        },
        "notes": [
            {
                "id": n.id,
                "order_uuid": n.order_uuid,
                "review_request_id": n.review_request_id,
                "note": n.note,
                "kind": n.kind,
                "created_at": n.created_at,
            }
            for n in notes
        ],
    }


# ---------- notes ----------

async def add_note(
    db: AsyncSession,
    user: User,
    order_uuid: UUID,
    note_text: str,
) -> ReviewRequestNote:
    # Confirm ownership of the order.
    order = (
        await db.execute(
            select(Order)
            .where(Order.id == order_uuid)
            .where(Order.user_id == user.id)
        )
    ).scalar_one_or_none()
    if order is None:
        raise APIError(404, "NOT_FOUND", "Order not found.")

    active = (
        await db.execute(
            select(ReviewRequest)
            .where(ReviewRequest.user_id == user.id)
            .where(ReviewRequest.order_uuid == order_uuid)
            .where(ReviewRequest.status.in_(["sent", "pending"]))
            .limit(1)
        )
    ).scalar_one_or_none()

    note = ReviewRequestNote(
        user_id=user.id,
        order_uuid=order_uuid,
        review_request_id=active.id if active else None,
        note=note_text,
        kind="user",
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


async def list_notes(
    db: AsyncSession, user: User, order_uuid: UUID
) -> list[ReviewRequestNote]:
    # Confirm ownership first.
    order = (
        await db.execute(
            select(Order)
            .where(Order.id == order_uuid)
            .where(Order.user_id == user.id)
        )
    ).scalar_one_or_none()
    if order is None:
        raise APIError(404, "NOT_FOUND", "Order not found.")

    return list(
        (
            await db.execute(
                select(ReviewRequestNote)
                .where(ReviewRequestNote.user_id == user.id)
                .where(ReviewRequestNote.order_uuid == order_uuid)
                .order_by(ReviewRequestNote.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
