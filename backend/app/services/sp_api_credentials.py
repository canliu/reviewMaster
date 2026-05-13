"""SP-API credentials CRUD with envelope encryption.

The seller stores: LWA client id (public-ish, kept as-is) + LWA client secret +
refresh token + selling-partner id + marketplace id. We encrypt the two
secrets at rest; the rest are kept plain so the UI can show them back without
a decryption step.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select  # noqa: F401  # used in list_credentials_for_user
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.models.seller_credential import SellerCredential
from app.services import crypto

# Marketplace token (the suffix in shop_site like "p3:US") → SP-API metadata.
MARKETPLACES: dict[str, dict[str, str]] = {
    "US": {"id": "ATVPDKIKX0DER", "label": "Amazon.com (US)"},
    "CA": {"id": "A2EUQ1WTGCTBG2", "label": "Amazon.ca (CA)"},
    "MX": {"id": "A1AM78C64UM0Y8", "label": "Amazon.com.mx (MX)"},
    "BR": {"id": "A2Q3Y263D00KWC", "label": "Amazon.com.br (BR)"},
    "UK": {"id": "A1F83G8C2ARO7P", "label": "Amazon.co.uk (UK)"},
    "GB": {"id": "A1F83G8C2ARO7P", "label": "Amazon.co.uk (GB)"},
    "DE": {"id": "A1PA6795UKMFR9", "label": "Amazon.de (DE)"},
    "FR": {"id": "A13V1IB3VIYZZH", "label": "Amazon.fr (FR)"},
    "IT": {"id": "APJ6JRA9NG5V4", "label": "Amazon.it (IT)"},
    "ES": {"id": "A1RKKUPIHCS9HS", "label": "Amazon.es (ES)"},
    "NL": {"id": "A1805IZSGTT6HS", "label": "Amazon.nl (NL)"},
    "SE": {"id": "A2NODRKZP88ZB9", "label": "Amazon.se (SE)"},
    "PL": {"id": "A1C3SOZRARQ6R3", "label": "Amazon.pl (PL)"},
    "TR": {"id": "A33AVAJ2PDY3EV", "label": "Amazon.com.tr (TR)"},
    "AE": {"id": "A2VIGQ35RCS4UG", "label": "Amazon.ae (AE)"},
    "SA": {"id": "A17E79C6D8DWNP", "label": "Amazon.sa (SA)"},
    "EG": {"id": "ARBP9OOSHTCHU", "label": "Amazon.eg (EG)"},
    "JP": {"id": "A1VC38T7YXB528", "label": "Amazon.co.jp (JP)"},
    "AU": {"id": "A39IBJ37TRP1C6", "label": "Amazon.com.au (AU)"},
    "SG": {"id": "A19VAU5U5O7RUS", "label": "Amazon.sg (SG)"},
    "IN": {"id": "A21TJRUUN4KGV", "label": "Amazon.in (IN)"},
}

# Reverse lookup by SP-API id.
_MARKETPLACE_BY_ID = {meta["id"]: token for token, meta in MARKETPLACES.items()}


def label_for_marketplace_id(marketplace_id: str) -> str:
    token = _MARKETPLACE_BY_ID.get(marketplace_id)
    if token is None:
        return marketplace_id
    return MARKETPLACES[token]["label"]


def validate_marketplace_id(marketplace_id: str) -> None:
    if marketplace_id not in _MARKETPLACE_BY_ID:
        raise APIError(
            422,
            "UNSUPPORTED_MARKETPLACE",
            f"Unknown marketplace_id '{marketplace_id}'. "
            f"Valid IDs: {sorted(_MARKETPLACE_BY_ID.keys())}",
        )


def market_token_for_shop_site(shop_site: str) -> str | None:
    """Helper: derive the marketplace token (e.g. 'US') from a shop_site string."""
    if not shop_site:
        return None
    if ":" in shop_site:
        token = shop_site.split(":", 1)[1]
    else:
        token = shop_site
    return token.strip().upper() or None


def marketplace_id_for_shop_site(shop_site: str) -> str | None:
    token = market_token_for_shop_site(shop_site)
    if token is None:
        return None
    meta = MARKETPLACES.get(token)
    return meta["id"] if meta else None


# ---------- save / load ----------


async def save_credentials(
    db: AsyncSession,
    user_id: UUID,
    shop_site: str,
    *,
    lwa_client_id: str,
    lwa_client_secret: str | None,
    refresh_token: str | None,
    selling_partner_id: str,
    marketplace_id: str,
) -> SellerCredential:
    """Save or update credentials for one (user, shop_site).

    Secrets are optional on UPDATE: if empty, the existing ciphertext is
    preserved so the user can adjust non-secret fields without re-pasting.
    On INSERT both secrets are required.
    """
    validate_marketplace_id(marketplace_id)
    if not shop_site or not shop_site.strip():
        raise APIError(422, "INVALID_SHOP_SITE", "shop_site is required.")
    shop_site = shop_site.strip()

    existing = await db.get(SellerCredential, (user_id, shop_site))

    if existing is None:
        if not lwa_client_secret or not refresh_token:
            raise APIError(
                422,
                "SECRETS_REQUIRED",
                "Both lwa_client_secret and refresh_token are required on first save.",
            )
        dek = crypto.generate_dek()
        row = SellerCredential(
            user_id=user_id,
            shop_site=shop_site,
            dek_encrypted=crypto.wrap_dek(dek, settings.encryption_kek),
            refresh_token_ciphertext=crypto.encrypt(refresh_token, dek),
            lwa_client_id=lwa_client_id,
            lwa_client_secret_ciphertext=crypto.encrypt(lwa_client_secret, dek),
            selling_partner_id=selling_partner_id,
            marketplace_id=marketplace_id,
        )
        db.add(row)
    else:
        if lwa_client_secret or refresh_token:
            new_dek = crypto.generate_dek()
            old_dek = crypto.unwrap_dek(existing.dek_encrypted, settings.encryption_kek)
            old_secret = crypto.decrypt(existing.lwa_client_secret_ciphertext, old_dek)
            old_refresh = crypto.decrypt(existing.refresh_token_ciphertext, old_dek)
            existing.dek_encrypted = crypto.wrap_dek(new_dek, settings.encryption_kek)
            existing.lwa_client_secret_ciphertext = crypto.encrypt(
                lwa_client_secret or old_secret, new_dek
            )
            existing.refresh_token_ciphertext = crypto.encrypt(
                refresh_token or old_refresh, new_dek
            )
        existing.lwa_client_id = lwa_client_id
        existing.selling_partner_id = selling_partner_id
        existing.marketplace_id = marketplace_id
        existing.updated_at = datetime.now(timezone.utc)
        row = existing
    await db.commit()
    await db.refresh(row)
    return row


async def load_credentials_for_shop(
    db: AsyncSession, user_id: UUID, shop_site: str
) -> SellerCredential | None:
    return await db.get(SellerCredential, (user_id, shop_site))


async def list_credentials_for_user(
    db: AsyncSession, user_id: UUID
) -> list[SellerCredential]:
    rows = (
        await db.execute(
            select(SellerCredential)
            .where(SellerCredential.user_id == user_id)
            .order_by(SellerCredential.shop_site)
        )
    ).scalars().all()
    return list(rows)


async def delete_credentials(
    db: AsyncSession, user_id: UUID, shop_site: str
) -> bool:
    row = await db.get(SellerCredential, (user_id, shop_site))
    if row is None:
        return False
    await db.delete(row)
    await db.commit()
    return True


def decrypt_credentials(row: SellerCredential) -> dict[str, str]:
    """Return a dict ready to feed into the SP-API client."""
    dek = crypto.unwrap_dek(row.dek_encrypted, settings.encryption_kek)
    return {
        "lwa_client_id": row.lwa_client_id,
        "lwa_client_secret": crypto.decrypt(row.lwa_client_secret_ciphertext, dek),
        "refresh_token": crypto.decrypt(row.refresh_token_ciphertext, dek),
        "selling_partner_id": row.selling_partner_id,
        "marketplace_id": row.marketplace_id,
    }


def metadata(row: SellerCredential) -> dict:
    """Safe-to-return metadata: never includes the secrets themselves."""
    return {
        "shop_site": row.shop_site,
        "configured": True,
        "lwa_client_id_prefix": row.lwa_client_id[:32],
        "selling_partner_id": row.selling_partner_id,
        "marketplace_id": row.marketplace_id,
        "marketplace_label": label_for_marketplace_id(row.marketplace_id),
        "updated_at": row.updated_at,
    }
