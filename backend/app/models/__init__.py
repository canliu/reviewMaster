"""SQLAlchemy ORM models.

`Base` is the declarative base shared by every model. Alembic imports this
module so `Base.metadata` reflects every table that's been declared.
"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Re-export every model so `from app.models import Base` is enough for Alembic
# to see all tables.
from app.models.buyer_product_stat import BuyerProductStat  # noqa: E402,F401
from app.models.order import Order  # noqa: E402,F401
from app.models.review_request import ReviewRequest  # noqa: E402,F401
from app.models.review_request_note import ReviewRequestNote  # noqa: E402,F401
from app.models.seller_credential import SellerCredential  # noqa: E402,F401
from app.models.upload_batch import UploadBatch  # noqa: E402,F401
from app.models.user import User  # noqa: E402,F401
from app.models.user_settings import UserSettings  # noqa: E402,F401
