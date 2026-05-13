"""Refresh `buyer_product_stats` for a set of affected groups.

Called by the upload worker after every batch lands. Runs one SQL upsert per
grain; the WHERE filters down to the (shop_site, buyer_key, group_value)
tuples affected by the batch so we don't re-aggregate the whole orders table.
"""
from __future__ import annotations

from typing import Iterable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

# Column on the `orders` table that backs each grain.
_GRAIN_COLUMN = {
    "asin": "asin",
    "spu": "spu",
    "product_name": "product_name",
}


def refresh_for_grain(
    session: Session,
    user_id: UUID,
    grain: str,
    tuples: Iterable[tuple[str, str, str]],
) -> None:
    """tuples is an iterable of (shop_site, buyer_key, group_value)."""
    column = _GRAIN_COLUMN[grain]
    rows = [
        {"shop_site": s, "buyer_key": b, "group_value": g}
        for s, b, g in tuples
        if g  # skip rows that don't have this grain's grouping column
    ]
    if not rows:
        return

    # Stash the affected tuples in a temporary table so the IN-list clause
    # doesn't balloon. Using `VALUES` inline would also work for small N,
    # but stage 2 expects 30k-row uploads.
    session.execute(text("CREATE TEMP TABLE IF NOT EXISTS _affected_tuples ("
                         "shop_site text, buyer_key text, group_value text) ON COMMIT DROP"))
    session.execute(text("TRUNCATE _affected_tuples"))
    session.execute(
        text(
            "INSERT INTO _affected_tuples (shop_site, buyer_key, group_value) "
            "VALUES (:shop_site, :buyer_key, :group_value)"
        ),
        rows,
    )

    sql = text(
        f"""
        INSERT INTO buyer_product_stats (
            user_id, shop_site, buyer_key, grain, group_value,
            order_count, first_order_at, last_order_at, total_amount, updated_at
        )
        SELECT o.user_id,
               o.shop_site,
               o.buyer_key,
               :grain AS grain,
               o.{column} AS group_value,
               COUNT(*),
               MIN(o.order_time_utc),
               MAX(o.order_time_utc),
               COALESCE(SUM(o.item_price * o.quantity), 0),
               NOW()
        FROM orders o
        JOIN _affected_tuples t
          ON t.shop_site = o.shop_site
         AND t.buyer_key = o.buyer_key
         AND t.group_value = o.{column}
        WHERE o.user_id = :user_id
          AND o.{column} IS NOT NULL
        GROUP BY o.user_id, o.shop_site, o.buyer_key, o.{column}
        ON CONFLICT (user_id, shop_site, buyer_key, grain, group_value)
        DO UPDATE SET order_count = EXCLUDED.order_count,
                      first_order_at = EXCLUDED.first_order_at,
                      last_order_at = EXCLUDED.last_order_at,
                      total_amount = EXCLUDED.total_amount,
                      updated_at = NOW()
        """
    )
    session.execute(sql, {"grain": grain, "user_id": user_id})
