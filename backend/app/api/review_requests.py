from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.errors import APIError
from app.models.user import User
from app.schemas.review_requests import (
    CreateRequestIn,
    CreateRequestOut,
    ReviewRequestDetail,
    ReviewRequestListItem,
    ReviewRequestListOut,
)
from app.services import review_requests as svc

router = APIRouter(prefix="/api/review-requests", tags=["review-requests"])


@router.post("", response_model=CreateRequestOut, status_code=201)
async def create_endpoint(
    body: CreateRequestIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CreateRequestOut:
    return CreateRequestOut(
        **(
            await svc.create_requests(
                db, user, body.order_uuids, body.method, body.note
            )
        )
    )


@router.get("", response_model=ReviewRequestListOut)
async def list_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    method: str | None = Query(None),
    status: str | None = Query(None),
    shop_site: str | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewRequestListOut:
    return ReviewRequestListOut(
        **(
            await svc.list_requests(
                db,
                user,
                page=page,
                page_size=page_size,
                method=method,
                status=status,
                shop_site=shop_site,
                from_date=from_date,
                to_date=to_date,
            )
        )
    )


# CSV export — must come BEFORE the /{id} catch-all so FastAPI matches it first.
@router.get("/export.csv")
async def export_csv(
    method: str | None = Query(None),
    status: str | None = Query(None),
    shop_site: str | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    # NOTE: we open a fresh session inside the generator instead of using
    # `Depends(get_db)`. FastAPI closes the request-scoped session as soon as
    # this handler returns the StreamingResponse, but the generator keeps
    # running afterwards — using the closed session raises mid-stream.
    columns = [
        "order_id", "shop_site", "asin", "product_name", "buyer_email", "buyer_key",
        "ship_city", "ship_state", "ship_country",
        "order_time_utc", "estimated_delivery_utc",
        "item_price", "currency", "quantity",
        "request_method", "request_status", "requested_at", "notes_count",
    ]
    user_id = user.id

    async def _rows() -> AsyncIterator[bytes]:
        from app.core.db import SessionLocal
        from sqlalchemy import select
        from app.models.order import Order
        from app.models.user import User as UserModel

        async with SessionLocal() as session:
            # Reload user inside this session so svc methods that access
            # user.id work without cross-session attachment issues.
            current_user = (
                await session.execute(
                    select(UserModel).where(UserModel.id == user_id)
                )
            ).scalar_one()

            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(columns)
            yield buf.getvalue().encode("utf-8")
            buf.seek(0)
            buf.truncate(0)

            page = 1
            page_size = 200
            while True:
                data = await svc.list_requests(
                    session,
                    current_user,
                    page=page,
                    page_size=page_size,
                    method=method,
                    status=status,
                    shop_site=shop_site,
                    from_date=from_date,
                    to_date=to_date,
                )
                if not data["items"]:
                    break
                order_uuids = [it["order_uuid"] for it in data["items"]]
                # Defense-in-depth: filter by user_id even though the IDs
                # come from a pre-filtered list. Prevents leakage if a future
                # refactor relaxes the upstream list's filter.
                orders_by_id = {
                    o.id: o
                    for o in (
                        await session.execute(
                            select(Order)
                            .where(Order.user_id == current_user.id)
                            .where(Order.id.in_(order_uuids))
                        )
                    )
                    .scalars()
                    .all()
                }
                for item in data["items"]:
                    o = orders_by_id.get(item["order_uuid"])
                    writer.writerow(
                        [
                            item["order_id"], item["shop_site"], item["asin"] or "",
                            item["product_name"] or "", item["buyer_email"] or "",
                            o.buyer_key if o else "",
                            o.ship_city if o else "",
                            o.ship_state if o else "",
                            o.ship_country if o else "",
                            o.order_time_utc.isoformat() if o and o.order_time_utc else "",
                            o.estimated_delivery_utc.isoformat() if o and o.estimated_delivery_utc else "",
                            str(o.item_price) if o and o.item_price is not None else "",
                            o.currency if o else "",
                            o.quantity if o else "",
                            item["method"], item["status"],
                            item["requested_at"].isoformat() if item["requested_at"] else "",
                            item["notes_count"],
                        ]
                    )
                yield buf.getvalue().encode("utf-8")
                buf.seek(0)
                buf.truncate(0)
                if len(data["items"]) < page_size:
                    break
                page += 1

    filename = f"review-requests-{date.today().isoformat()}.csv"
    return StreamingResponse(
        _rows(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{request_id}", response_model=ReviewRequestDetail)
async def detail_endpoint(
    request_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewRequestDetail:
    result = await svc.detail(db, user, request_id)
    if result is None:
        raise APIError(404, "NOT_FOUND", "Review request not found.")
    return ReviewRequestDetail(**result)


@router.patch("/{request_id}/confirm", response_model=ReviewRequestListItem)
async def confirm_endpoint(
    request_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewRequestListItem:
    await svc.confirm(db, user, request_id)
    detail = await svc.detail(db, user, request_id)
    assert detail is not None
    return ReviewRequestListItem(**detail["request"])


@router.patch("/{request_id}/confirm-as-manual", response_model=ReviewRequestListItem)
async def confirm_as_manual_endpoint(
    request_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewRequestListItem:
    await svc.confirm_as_manual(db, user, request_id)
    detail = await svc.detail(db, user, request_id)
    assert detail is not None
    return ReviewRequestListItem(**detail["request"])
