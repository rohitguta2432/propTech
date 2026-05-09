"""initial schema — 7 tables

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-09

Source of truth: specs/database.md
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET, JSONB

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------- checks ----------------
    op.create_table(
        "checks",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("portal", sa.Text, nullable=False),
        sa.Column("listing_id", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("red_flags", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("green_flags", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("checklist", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("verifications", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("property_data", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("cache_hit", sa.Boolean, nullable=False, server_default=sa.text("FALSE")),
        sa.Column("source_surface", sa.Text, nullable=False),
        sa.Column("requester_ip", INET, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("checked_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("score BETWEEN 0 AND 100", name="checks_score_range"),
        sa.CheckConstraint("label IN ('safe','caution','risky')", name="checks_label_enum"),
        sa.CheckConstraint(
            "source_surface IN ('web','extension','whatsapp','api')",
            name="checks_source_surface_enum",
        ),
    )
    op.create_index("idx_checks_portal_listing", "checks", ["portal", "listing_id"])
    op.create_index("idx_checks_checked_at", "checks", [sa.text("checked_at DESC")])
    op.create_index("idx_checks_score", "checks", ["score"])

    # ---------------- properties ----------------
    op.create_table(
        "properties",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("portal", sa.Text, nullable=False),
        sa.Column("listing_id", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("price_inr", sa.BigInteger, nullable=True),
        sa.Column("bhk", sa.SmallInteger, nullable=True),
        sa.Column("area_sqft", sa.Integer, nullable=True),
        sa.Column("locality", sa.Text, nullable=True),
        sa.Column("city", sa.Text, nullable=True),
        sa.Column("state", sa.Text, nullable=True),
        sa.Column("rera_id", sa.Text, nullable=True),
        sa.Column("builder_name", sa.Text, nullable=True),
        sa.Column("listed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("images", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("raw", JSONB, nullable=True),
        sa.Column("first_seen", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("portal", "listing_id", name="properties_portal_listing_unique"),
    )
    op.create_index("idx_properties_locality_bhk", "properties", ["city", "locality", "bhk"])
    op.create_index(
        "idx_properties_rera",
        "properties",
        ["rera_id"],
        postgresql_where=sa.text("rera_id IS NOT NULL"),
    )
    op.create_index(
        "idx_properties_builder",
        "properties",
        ["builder_name"],
        postgresql_where=sa.text("builder_name IS NOT NULL"),
    )

    # ---------------- images ----------------
    op.create_table(
        "images",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "property_id",
            sa.BigInteger,
            sa.ForeignKey("properties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("phash", sa.BigInteger, nullable=False),
        sa.Column("sha256", sa.Text, nullable=True),
        sa.Column("width", sa.Integer, nullable=True),
        sa.Column("height", sa.Integer, nullable=True),
        sa.Column("first_seen", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_images_phash", "images", ["phash"])

    # ---------------- locality_prices ----------------
    op.create_table(
        "locality_prices",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("city", sa.Text, nullable=False),
        sa.Column("locality", sa.Text, nullable=False),
        sa.Column("bhk", sa.SmallInteger, nullable=False),
        sa.Column("avg_price_per_sqft", sa.Integer, nullable=False),
        sa.Column("sample_size", sa.Integer, nullable=False),
        sa.Column("refreshed_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("city", "locality", "bhk", name="locality_prices_unique"),
    )

    # ---------------- rera_records ----------------
    op.create_table(
        "rera_records",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("state", sa.Text, nullable=False),
        sa.Column("rera_id", sa.Text, nullable=False),
        sa.Column("project_name", sa.Text, nullable=True),
        sa.Column("builder_name", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=True),
        sa.Column("raw", JSONB, nullable=True),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("state", "rera_id", name="rera_state_rera_unique"),
    )
    op.create_index("idx_rera_builder", "rera_records", ["builder_name"])

    # ---------------- builder_complaints ----------------
    op.create_table(
        "builder_complaints",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("builder_name", sa.Text, nullable=False),
        sa.Column("state", sa.Text, nullable=False),
        sa.Column("open_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("closed_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("delays_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("last_complaint_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("refreshed_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("builder_name", "state", name="builder_complaints_unique"),
    )

    # ---------------- feedback ----------------
    op.create_table(
        "feedback",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("check_id", sa.Text, sa.ForeignKey("checks.id"), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("reporter_email", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','reviewed','accepted','rejected')",
            name="feedback_status_enum",
        ),
    )


def downgrade() -> None:
    op.drop_table("feedback")
    op.drop_table("builder_complaints")
    op.drop_index("idx_rera_builder", table_name="rera_records")
    op.drop_table("rera_records")
    op.drop_table("locality_prices")
    op.drop_index("idx_images_phash", table_name="images")
    op.drop_table("images")
    op.drop_index("idx_properties_builder", table_name="properties")
    op.drop_index("idx_properties_rera", table_name="properties")
    op.drop_index("idx_properties_locality_bhk", table_name="properties")
    op.drop_table("properties")
    op.drop_index("idx_checks_score", table_name="checks")
    op.drop_index("idx_checks_checked_at", table_name="checks")
    op.drop_index("idx_checks_portal_listing", table_name="checks")
    op.drop_table("checks")
