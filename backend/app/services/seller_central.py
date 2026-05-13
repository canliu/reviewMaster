"""Seller Central order-page URL builder.

Important: there is **no** deep link directly to the "Request a Review"
button in Seller Central — Amazon only exposes the order detail page URL.
The frontend's confirmation modal must instruct the seller to click that
button on the page they land on. This function returns the order URL only.
"""
from __future__ import annotations

from app.core.errors import APIError

# Marketplace token → seller central TLD. Token is the suffix after `:`
# in shop_site (e.g. "p3:US" → "US"). Keep this in sync with the table in
# stage_5_request.md.
_TLD_BY_MARKET: dict[str, str] = {
    "US": "com",
    "CA": "ca",
    "MX": "com.mx",
    "BR": "com.br",
    "UK": "co.uk",
    "GB": "co.uk",  # alias
    "DE": "de",
    "FR": "fr",
    "IT": "it",
    "ES": "es",
    "NL": "nl",
    "SE": "se",
    "PL": "pl",
    "TR": "com.tr",
    "AE": "ae",
    "SA": "sa",
    "EG": "eg",
    "JP": "co.jp",
    "AU": "com.au",
    "SG": "sg",
    "IN": "in",
}


def market_from_shop_site(shop_site: str) -> str:
    """Return the uppercase marketplace token from `shop_site`.

    Accepts `p3:US` style or a bare market code. Anything that doesn't
    resolve to a known TLD raises an APIError.
    """
    if not shop_site:
        raise APIError(
            422,
            "UNSUPPORTED_MARKETPLACE",
            "Empty shop_site has no associated marketplace.",
        )
    if ":" in shop_site:
        token = shop_site.split(":", 1)[1]
    else:
        token = shop_site
    token = token.strip().upper()
    if token not in _TLD_BY_MARKET:
        raise APIError(
            422,
            "UNSUPPORTED_MARKETPLACE",
            f"Marketplace '{token}' is not supported. "
            f"Known: {sorted(_TLD_BY_MARKET.keys())}.",
        )
    return token


def build_seller_central_url(shop_site: str, order_id: str) -> str:
    """Build the order-detail URL on Seller Central for the order's market."""
    market = market_from_shop_site(shop_site)
    tld = _TLD_BY_MARKET[market]
    return f"https://sellercentral.amazon.{tld}/orders-v3/order/{order_id}"
