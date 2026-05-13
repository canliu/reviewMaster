"""RQ job: submit a productReviewAndSellerFeedback solicitation via SP-API.

The job is intentionally short — most complexity lives in the helpers:
  * `app.services.rate_limit.solicitations_bucket()` — Redis token bucket.
  * `app.services.sp_api_client.call_solicitations(...)` — single seam for tests.
  * `_map_exception(...)` — decodes Amazon errors into our catalog.

See ``ERROR_CODES`` for the user-facing translation; the prompt's catalog is
the contract.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from tenacity import (
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.logger import get_logger
from app.models.review_request import ReviewRequest
from app.models.order import Order
from app.services import sp_api_client, sp_api_credentials
from app.services.rate_limit import solicitations_bucket
from app.workers.db import SyncSessionLocal

logger = get_logger(__name__)


ERROR_CODES: dict[str, str] = {
    "OUT_OF_WINDOW": "Order is outside the 5–30 day window.",
    "ORDER_NOT_FOUND": "Amazon doesn't recognize this order ID.",
    "ALREADY_SOLICITED": "Amazon reports a review has already been requested for this order.",
    "ALREADY_SOLICITED_BY_AMAZON": (
        "Amazon reports a review has already been requested for this order "
        "by another tool or manually."
    ),
    "INELIGIBLE_ORDER": (
        "Amazon won't accept review requests for this order (cancelled, refunded, etc.)."
    ),
    "INVALID_REFRESH_TOKEN": (
        "Your refresh token is invalid or revoked. Please reconnect in Settings."
    ),
    "RATE_LIMITED": "Amazon rate-limited the request. We'll retry automatically.",
    "MARKETPLACE_MISMATCH": (
        "The order's marketplace isn't authorized in your SP-API app."
    ),
    "NETWORK_ERROR": "We couldn't reach Amazon. Please try again later.",
    "UNKNOWN": "Something went wrong. Check the details below.",
}


def _is_retryable(exc: BaseException) -> bool:
    """Network failures and 429/5xx → retry. Everything else → fail fast."""
    code = _classify_exception(exc)
    return code in ("RATE_LIMITED", "NETWORK_ERROR")


def send_solicitation(review_request_id: str) -> None:
    """RQ entrypoint. Always settles ``review_request.status`` — never leaves
    pending if anything happens we can detect."""
    rr_id = UUID(review_request_id)
    with SyncSessionLocal() as session:
        rr = session.get(ReviewRequest, rr_id)
        if rr is None:
            logger.warning("review_request %s not found; nothing to do", rr_id)
            return
        order = session.get(Order, rr.order_uuid)
        if order is None:
            _mark_failed(session, rr, code="UNKNOWN", message="Order missing.")
            return

        from app.models.seller_credential import SellerCredential

        # Per-shop creds — look up by (user, order.shop_site).
        cred_row = session.get(SellerCredential, (rr.user_id, order.shop_site))
        if cred_row is None:
            _mark_failed(
                session,
                rr,
                code="SP_API_NOT_CONFIGURED",
                message=(
                    f"No SP-API credentials configured for shop '{order.shop_site}'."
                ),
            )
            return

        creds = sp_api_credentials.decrypt_credentials(cred_row)
        order_marketplace = cred_row.marketplace_id

    # Rate-limit (block up to 60s).
    if not solicitations_bucket().acquire(timeout=60.0):
        # Nothing we can do; re-enqueue would be ideal but for MVP we mark failed.
        with SyncSessionLocal() as session:
            rr = session.get(ReviewRequest, rr_id)
            if rr is not None:
                _mark_failed(
                    session, rr, code="RATE_LIMITED",
                    message="Couldn't acquire a rate-limit slot within 60s.",
                )
        return

    # Submit with tenacity-driven retry on transient errors.
    response: Any | None = None
    last_exc: BaseException | None = None
    try:
        for attempt in Retrying(
            retry=retry_if_exception(_is_retryable),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=2, min=2, max=15),
            reraise=True,
        ):
            with attempt:
                response = sp_api_client.call_solicitations(
                    creds,
                    amazon_order_id=order.order_id,
                    marketplace_id=order_marketplace,
                )
    except BaseException as exc:  # noqa: BLE001
        last_exc = exc

    with SyncSessionLocal() as session:
        rr = session.get(ReviewRequest, rr_id)
        if rr is None:
            return
        if last_exc is None:
            rr.status = "sent"
            rr.api_response = {"payload": _as_jsonable(response)}
            rr.error_code = None
        else:
            code = _classify_exception(last_exc)
            if code == "ALREADY_SOLICITED":
                # Treat as success per stage 6 spec: Amazon's intent-satisfied case.
                rr.status = "sent"
                rr.error_code = "ALREADY_SOLICITED_BY_AMAZON"
                rr.api_response = {"error": str(last_exc), "code": code}
            else:
                rr.status = "failed"
                rr.error_code = code
                rr.api_response = {"error": str(last_exc), "code": code}
        rr.updated_at = datetime.now(timezone.utc)
        session.commit()


# ---------- helpers ----------


def _mark_failed(
    session: Session, rr: ReviewRequest, *, code: str, message: str
) -> None:
    rr.status = "failed"
    rr.error_code = code
    rr.api_response = {"error": message, "code": code}
    rr.updated_at = datetime.now(timezone.utc)
    session.commit()


def _classify_exception(exc: BaseException) -> str:
    """Best-effort mapping from SP-API library exceptions to our codes.

    Check the exception's TEXT content first for unambiguous markers
    (throttled, 429, timeout) since those classify the same regardless of
    which library exception class wraps them. Then fall back to class-name
    heuristics.
    """
    name = type(exc).__name__
    text = str(exc).lower()

    # Text-content first: these markers dominate the type hierarchy.
    if "throttle" in text or " 429" in text or text.startswith("429") or "rate" in text and "limit" in text:
        return "RATE_LIMITED"
    if "timeout" in text or "connection" in text or "network" in text:
        return "NETWORK_ERROR"

    if name in {"SellingApiBadRequestException", "SellingApiRequestException"}:
        if "already" in text or ("solicit" in text and "already" in text):
            return "ALREADY_SOLICITED"
        if "not eligible" in text or "ineligible" in text:
            return "INELIGIBLE_ORDER"
        if "not found" in text or "no such order" in text:
            return "ORDER_NOT_FOUND"
        if "out of window" in text or "delivery" in text:
            return "OUT_OF_WINDOW"
        if "unauthorized" in text or "not authorized" in text or "marketplace" in text:
            return "MARKETPLACE_MISMATCH"
        return "UNKNOWN"
    if name in {"SellingApiForbiddenException", "SellingApiUnauthorizedException"}:
        if "refresh" in text or "token" in text:
            return "INVALID_REFRESH_TOKEN"
        return "MARKETPLACE_MISMATCH"
    if name in {
        "SellingApiServerException",
        "SellingApiTemporarilyUnavailableException",
    }:
        return "NETWORK_ERROR"

    return "UNKNOWN"


def _as_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list, str, int, float, bool)):
        return value
    return str(value)
