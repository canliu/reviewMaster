"""initial schema — all 8 tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-12

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------- users ----------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False, server_default="UTC"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ---------- user_settings ----------
    op.create_table(
        "user_settings",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("active_shop_site", sa.String(), nullable=True),
        sa.Column(
            "repeat_grain",
            sa.String(),
            nullable=False,
            server_default="asin",
        ),
        sa.Column(
            "excluded_order_types",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "repeat_grain IN ('asin', 'spu', 'product_name')",
            name="user_settings_repeat_grain_check",
        ),
    )

    # ---------- orders ----------
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("shop_site", sa.String(), nullable=False),
        sa.Column("asin", sa.String(), nullable=True),
        sa.Column("msku", sa.String(), nullable=True),
        sa.Column("sku", sa.String(), nullable=True),
        sa.Column("spu", sa.String(), nullable=True),
        sa.Column("product_name", sa.String(), nullable=True),
        sa.Column("product_title", sa.String(), nullable=True),
        sa.Column("parent_product_name", sa.String(), nullable=True),
        sa.Column("order_type", sa.String(), nullable=True),
        sa.Column("buyer_email", sa.String(), nullable=True),
        sa.Column("buyer_key", sa.String(), nullable=False),
        sa.Column("order_time_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ship_time_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_delivery_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("item_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("ship_city", sa.String(), nullable=True),
        sa.Column("ship_state", sa.String(), nullable=True),
        sa.Column("ship_country", sa.String(), nullable=True),
        sa.Column("tracking_number", sa.String(), nullable=True),
        sa.Column("carrier", sa.String(), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "order_id", name="orders_user_id_order_id_key"),
    )
    op.create_index(
        "orders_user_shop_buyer_asin_idx",
        "orders",
        ["user_id", "shop_site", "buyer_key", "asin"],
    )
    op.create_index(
        "orders_user_shop_buyer_spu_idx",
        "orders",
        ["user_id", "shop_site", "buyer_key", "spu"],
    )
    op.create_index(
        "orders_user_eta_idx",
        "orders",
        ["user_id", "estimated_delivery_utc"],
    )
    op.create_index(
        "orders_user_shop_idx",
        "orders",
        ["user_id", "shop_site"],
    )

    # ---------- buyer_product_stats ----------
    op.create_table(
        "buyer_product_stats",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shop_site", sa.String(), nullable=False),
        sa.Column("buyer_key", sa.String(), nullable=False),
        sa.Column("grain", sa.String(), nullable=False),
        sa.Column("group_value", sa.String(), nullable=False),
        sa.Column("order_count", sa.Integer(), nullable=False),
        sa.Column("first_order_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_order_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "shop_site", "buyer_key", "grain", "group_value"
        ),
        sa.CheckConstraint(
            "grain IN ('asin', 'spu', 'product_name')",
            name="buyer_product_stats_grain_check",
        ),
    )
    op.create_index(
        "buyer_stats_user_shop_grain_count_idx",
        "buyer_product_stats",
        ["user_id", "shop_site", "grain", "order_count"],
    )

    # ---------- review_requests ----------
    op.create_table(
        "review_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("api_response", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id", "order_uuid", name="review_requests_user_id_order_uuid_key"
        ),
        sa.CheckConstraint(
            "method IN ('manual', 'link', 'api')",
            name="review_requests_method_check",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed')",
            name="review_requests_status_check",
        ),
    )

    # ---------- review_request_notes ----------
    op.create_table(
        "review_request_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Intentionally NOT a foreign key — preserves the id string for forensic
        # queries even after the review_request row is deleted on retry.
        sa.Column("review_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "kind IN ('user', 'system')",
            name="review_request_notes_kind_check",
        ),
    )
    op.create_index(
        "review_request_notes_user_order_created_idx",
        "review_request_notes",
        ["user_id", "order_uuid", sa.text("created_at DESC")],
    )

    # ---------- upload_batches ----------
    op.create_table(
        "upload_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_detail", postgresql.JSONB(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('processing', 'completed', 'failed')",
            name="upload_batches_status_check",
        ),
    )

    # ---------- seller_credentials ----------
    op.create_table(
        "seller_credentials",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("dek_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("refresh_token_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("lwa_client_id", sa.String(), nullable=False),
        sa.Column("lwa_client_secret_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("selling_partner_id", sa.String(), nullable=False),
        sa.Column("marketplace_id", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("seller_credentials")
    op.drop_table("upload_batches")
    op.drop_index(
        "review_request_notes_user_order_created_idx",
        table_name="review_request_notes",
    )
    op.drop_table("review_request_notes")
    op.drop_table("review_requests")
    op.drop_index(
        "buyer_stats_user_shop_grain_count_idx", table_name="buyer_product_stats"
    )
    op.drop_table("buyer_product_stats")
    op.drop_index("orders_user_shop_idx", table_name="orders")
    op.drop_index("orders_user_eta_idx", table_name="orders")
    op.drop_index("orders_user_shop_buyer_spu_idx", table_name="orders")
    op.drop_index("orders_user_shop_buyer_asin_idx", table_name="orders")
    op.drop_table("orders")
    op.drop_table("user_settings")
    op.drop_table("users")
