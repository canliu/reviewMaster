from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CredentialsIn(BaseModel):
    lwa_client_id: str = Field(min_length=1)
    # Secrets are optional on UPDATE — if the row exists and the client
    # leaves them blank, the existing ciphertext is preserved. The service
    # layer enforces "required on first save".
    lwa_client_secret: str | None = Field(default=None)
    refresh_token: str | None = Field(default=None)
    selling_partner_id: str = Field(min_length=1)
    marketplace_id: str = Field(min_length=1)


class CredentialsMetadataOut(BaseModel):
    configured: bool
    lwa_client_id_prefix: str | None = None
    selling_partner_id: str | None = None
    marketplace_id: str | None = None
    marketplace_label: str | None = None
    updated_at: datetime | None = None


class TestConnectionOk(BaseModel):
    ok: Literal[True] = True
    marketplaces: list[str]
    elapsed_ms: int


class TestConnectionFail(BaseModel):
    ok: Literal[False] = False
    error_code: str
    message: str
