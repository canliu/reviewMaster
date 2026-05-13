"""per-shop SP-API credentials

Revision ID: 0003_per_shop_credentials
Revises: 0002_error_code
Create Date: 2026-05-13

Previously `seller_credentials` had PK (user_id) — one credential set per
user across all marketplaces. Sellers actually manage one Amazon developer
app per shop, so we make the row keyed by (user_id, shop_site).

Existing rows are deleted; the prompt and the credentials UI are clear that
this is a fresh model. Dev databases re-enter creds; no production data
existed at this revision.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_per_shop_credentials"
down_revision: Union[str, None] = "0002_error_code"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop all existing rows so the (user_id, shop_site) PK can be created
    # without backfilling. There's no production data at this revision.
    op.execute("DELETE FROM seller_credentials")
    op.drop_constraint("seller_credentials_pkey", "seller_credentials", type_="primary")
    op.add_column(
        "seller_credentials",
        sa.Column("shop_site", sa.String(), nullable=False),
    )
    op.create_primary_key(
        "seller_credentials_pkey",
        "seller_credentials",
        ["user_id", "shop_site"],
    )


def downgrade() -> None:
    op.execute("DELETE FROM seller_credentials")
    op.drop_constraint("seller_credentials_pkey", "seller_credentials", type_="primary")
    op.drop_column("seller_credentials", "shop_site")
    op.create_primary_key(
        "seller_credentials_pkey",
        "seller_credentials",
        ["user_id"],
    )
