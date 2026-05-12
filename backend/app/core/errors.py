from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class APIError(Exception):
    """Application error with a stable error code.

    The handler emits `{"detail": message, "code": code}` so the frontend can
    pattern-match on `code` without parsing English messages.
    """

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(APIError, _api_error_handler)  # type: ignore[arg-type]
