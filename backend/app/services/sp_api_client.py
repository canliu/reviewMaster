"""Thin wrapper around python-amazon-sp-api.

Centralising the SP-API client surface lets tests monkey-patch a single
seam (``call_solicitations`` / ``call_marketplace_participations``) instead
of mocking the library internals everywhere.
"""
from __future__ import annotations

from typing import Any

# Imports from the library are deferred to avoid hitting boto3-style init on
# module import — keeps the test environment fast and lets us monkey-patch
# the entry points cleanly.


def _client_kwargs(creds: dict[str, str]) -> dict[str, Any]:
    return {
        "credentials": {
            "lwa_app_id": creds["lwa_client_id"],
            "lwa_client_secret": creds["lwa_client_secret"],
            "refresh_token": creds["refresh_token"],
        },
        "marketplace": _marketplace_obj(creds["marketplace_id"]),
    }


def _marketplace_obj(marketplace_id: str):
    """Pick the right Marketplaces enum value from the library."""
    from sp_api.base import Marketplaces  # type: ignore[import-not-found]

    for member in Marketplaces:
        if member.marketplace_id == marketplace_id:  # type: ignore[attr-defined]
            return member
    return Marketplaces.US  # type: ignore[attr-defined]


def call_marketplace_participations(creds: dict[str, str]) -> dict[str, Any]:
    """Used by the test-connection endpoint to confirm credentials work."""
    from sp_api.api import Sellers  # type: ignore[import-not-found]

    client = Sellers(**_client_kwargs(creds))
    return client.get_marketplace_participation().payload  # type: ignore[no-any-return]


def call_solicitations(
    creds: dict[str, str], *, amazon_order_id: str, marketplace_id: str
) -> dict[str, Any]:
    """Request a productReviewAndSellerFeedback solicitation for an order.

    Raises whatever the library raises (typically `SellingApiException` with
    a `code` attribute we can pattern-match on).
    """
    from sp_api.api import Solicitations  # type: ignore[import-not-found]

    client = Solicitations(**_client_kwargs(creds))
    return client.create_product_review_and_seller_feedback_solicitation(  # type: ignore[no-any-return]
        order_id=amazon_order_id,
        marketplace_ids=[marketplace_id],
    ).payload
