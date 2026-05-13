"""add error_code to review_requests

Revision ID: 0002_error_code
Revises: 0001_initial
Create Date: 2026-05-13

Tracks the decoded error_code from SP-API failures so the UI can show a
user-readable message rather than the raw Amazon error.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_error_code"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "review_requests",
        sa.Column("error_code", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("review_requests", "error_code")
