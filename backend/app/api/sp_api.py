from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.errors import APIError
from app.models.user import User
from app.schemas.sp_api import (
    CredentialsIn,
    CredentialsMetadataOut,
    TestConnectionFail,
    TestConnectionOk,
)
from app.services import sp_api_client, sp_api_credentials
from app.workers.solicitations import _classify_exception

router = APIRouter(prefix="/api/sp-api", tags=["sp-api"])


@router.get("/credentials", response_model=CredentialsMetadataOut)
async def get_credentials(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CredentialsMetadataOut:
    row = await sp_api_credentials.load_credentials(db, user.id)
    if row is None:
        return CredentialsMetadataOut(configured=False)
    return CredentialsMetadataOut(**sp_api_credentials.metadata(row))


@router.post(
    "/credentials",
    response_model=CredentialsMetadataOut,
    status_code=status.HTTP_201_CREATED,
)
async def save_credentials(
    body: CredentialsIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CredentialsMetadataOut:
    row = await sp_api_credentials.save_credentials(
        db,
        user.id,
        lwa_client_id=body.lwa_client_id,
        lwa_client_secret=body.lwa_client_secret,
        refresh_token=body.refresh_token,
        selling_partner_id=body.selling_partner_id,
        marketplace_id=body.marketplace_id,
    )
    return CredentialsMetadataOut(**sp_api_credentials.metadata(row))


@router.delete("/credentials", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credentials(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await sp_api_credentials.delete_credentials(db, user.id)
    if not deleted:
        raise APIError(404, "NOT_FOUND", "No SP-API credentials configured.")


@router.post("/test-connection")
async def test_connection(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    row = await sp_api_credentials.load_credentials(db, user.id)
    if row is None:
        return JSONResponse(
            status_code=422,
            content=TestConnectionFail(
                error_code="SP_API_NOT_CONFIGURED",
                message="Save your SP-API credentials first.",
            ).model_dump(),
        )

    creds = sp_api_credentials.decrypt_credentials(row)
    started = time.monotonic()
    try:
        payload = sp_api_client.call_marketplace_participations(creds)
    except BaseException as exc:  # noqa: BLE001
        code = _classify_exception(exc)
        return JSONResponse(
            status_code=200,
            content=TestConnectionFail(error_code=code, message=str(exc)).model_dump(),
        )

    elapsed_ms = int((time.monotonic() - started) * 1000)
    marketplaces: list[str] = []
    # SP-API getMarketplaceParticipation returns a list of dicts; pull out ids.
    if isinstance(payload, list):
        for item in payload:
            mp = (item or {}).get("marketplace") if isinstance(item, dict) else None
            if isinstance(mp, dict) and "id" in mp:
                marketplaces.append(mp["id"])
    return TestConnectionOk(marketplaces=marketplaces, elapsed_ms=elapsed_ms)
