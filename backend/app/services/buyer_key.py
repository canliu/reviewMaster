"""Derivation rule for the canonical buyer identifier.

Repeat-buyer detection scopes by `(user_id, shop_site, buyer_key)`. This
function is the SINGLE source of truth for what `buyer_key` looks like —
both the upload worker and any future re-keying job must use it.
"""
from __future__ import annotations

import hashlib


def derive_buyer_key(
    buyer_email: str | None,
    shop_site: str | None,
    ship_country: str | None,
    ship_state: str | None,
    ship_city: str | None,
) -> str:
    """Return the buyer_key for a single order row.

    * If `buyer_email` is present and non-empty:
        ``buyer_key = "email:" + lowercase(buyer_email)``
    * Otherwise (no email — common for some marketplaces):
        ``buyer_key = "addr:" + sha256(shop_site|country|state|city)``
      where each component is stripped + lowercased and missing values
      become the empty string.
    """
    if buyer_email and buyer_email.strip():
        return "email:" + buyer_email.strip().lower()

    def _norm(value: str | None) -> str:
        return (value or "").strip().lower()

    composite = "|".join(
        [_norm(shop_site), _norm(ship_country), _norm(ship_state), _norm(ship_city)]
    )
    digest = hashlib.sha256(composite.encode("utf-8")).hexdigest()
    return "addr:" + digest
