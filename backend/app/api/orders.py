from __future__ import annotations

import csv
import io
from datetime import date
from typing import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.errors import APIError
from app.models.order import Order
from app.models.review_request import ReviewRequest
from app.models.user import User
from app.schemas.notes import CreateNoteIn
from app.schemas.review_requests import NoteOut
from app.services import review_requests as svc
from app.models.user_settings import UserSettings


router = APIRouter(tags=["orders"])


@router.post("/api/orders/{order_uuid}/notes", response_model=NoteOut, status_code=201)
async def add_note(
    order_uuid: UUID,
    body: CreateNoteIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteOut:
    note = await svc.add_note(db, user, order_uuid, body.note)
    return NoteOut(
        id=note.id,
        order_uuid=note.order_uuid,
        review_request_id=note.review_request_id,
        note=note.note,
        kind=note.kind,
        created_at=note.created_at,
    )


@router.get("/api/orders/{order_uuid}/notes", response_model=list[NoteOut])
async def list_notes(
    order_uuid: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NoteOut]:
    notes = await svc.list_notes(db, user, order_uuid)
    return [
        NoteOut(
            id=n.id,
            order_uuid=n.order_uuid,
            review_request_id=n.review_request_id,
            note=n.note,
            kind=n.kind,
            created_at=n.created_at,
        )
        for n in notes
    ]


# ---- Buyer-history CSV export ----


@router.get("/api/buyers/{buyer_key}/orders.csv")
async def buyer_orders_csv(
    buyer_key: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    settings_row = await db.get(UserSettings, user.id)
    if settings_row is None or settings_row.active_shop_site is None:
        raise APIError(422, "NO_ACTIVE_SHOP", "Set an active shop first.")
    shop = settings_row.active_shop_site

    orders = (
        (
            await db.execute(
                select(Order)
                .where(Order.user_id == user.id)
                .where(Order.shop_site == shop)
                .where(Order.buyer_key == buyer_key)
                .order_by(Order.order_time_utc.desc())
            )
        )
        .scalars()
        .all()
    )

    # Active reviews lookup
    review_lookup: dict[UUID, ReviewRequest] = {
        r.order_uuid: r
        for r in (
            await db.execute(
                select(ReviewRequest)
                .where(ReviewRequest.user_id == user.id)
                .where(ReviewRequest.order_uuid.in_([o.id for o in orders]))
            )
        )
        .scalars()
        .all()
    }

    columns = [
        "order_id", "shop_site", "asin", "product_name", "buyer_email", "buyer_key",
        "ship_city", "ship_state", "ship_country",
        "order_time_utc", "estimated_delivery_utc",
        "item_price", "currency", "quantity",
        "request_method", "request_status",
    ]

    async def _rows() -> AsyncIterator[bytes]:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(columns)
        yield buf.getvalue().encode("utf-8")
        buf.seek(0)
        buf.truncate(0)

        for o in orders:
            r = review_lookup.get(o.id)
            writer.writerow(
                [
                    o.order_id, o.shop_site, o.asin or "", o.product_name or "",
                    o.buyer_email or "", o.buyer_key,
                    o.ship_city or "", o.ship_state or "", o.ship_country or "",
                    o.order_time_utc.isoformat() if o.order_time_utc else "",
                    o.estimated_delivery_utc.isoformat() if o.estimated_delivery_utc else "",
                    str(o.item_price) if o.item_price is not None else "",
                    o.currency or "",
                    o.quantity if o.quantity is not None else "",
                    r.method if r else "",
                    r.status if r else "",
                ]
            )
        yield buf.getvalue().encode("utf-8")

    filename = f"buyer-{buyer_key.split(':', 1)[-1][:16]}-{date.today().isoformat()}.csv"
    return StreamingResponse(
        _rows(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
