"""SQLAlchemy ORM mappings.

Mirrors specs/database.md and migrations/versions/*. Update both in the same PR.
"""
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Check(Base):
    __tablename__ = "checks"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="checks_score_range"),
        CheckConstraint("label IN ('safe','caution','risky')", name="checks_label_enum"),
        CheckConstraint(
            "source_surface IN ('web','extension','whatsapp','api')",
            name="checks_source_surface_enum",
        ),
        Index("idx_checks_portal_listing", "portal", "listing_id"),
        Index("idx_checks_checked_at", "checked_at"),
        Index("idx_checks_score", "score"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    portal: Mapped[str] = mapped_column(Text, nullable=False)
    listing_id: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    red_flags: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    green_flags: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    checklist: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    verifications: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    property_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_surface: Mapped[str] = mapped_column(Text, nullable=False)
    requester_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Property(Base):
    __tablename__ = "properties"
    __table_args__ = (
        UniqueConstraint("portal", "listing_id", name="properties_portal_listing_unique"),
        Index("idx_properties_locality_bhk", "city", "locality", "bhk"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    portal: Mapped[str] = mapped_column(Text, nullable=False)
    listing_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_inr: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    bhk: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    area_sqft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    locality: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str | None] = mapped_column(Text, nullable=True)
    rera_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    builder_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    listed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    images: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Image(Base):
    __tablename__ = "images"
    __table_args__ = (Index("idx_images_phash", "phash"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    phash: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LocalityPrice(Base):
    __tablename__ = "locality_prices"
    __table_args__ = (UniqueConstraint("city", "locality", "bhk", name="locality_prices_unique"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    locality: Mapped[str] = mapped_column(Text, nullable=False)
    bhk: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    avg_price_per_sqft: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RERARecord(Base):
    __tablename__ = "rera_records"
    __table_args__ = (
        UniqueConstraint("state", "rera_id", name="rera_state_rera_unique"),
        Index("idx_rera_builder", "builder_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    rera_id: Mapped[str] = mapped_column(Text, nullable=False)
    project_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    builder_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BuilderComplaint(Base):
    __tablename__ = "builder_complaints"
    __table_args__ = (UniqueConstraint("builder_name", "state", name="builder_complaints_unique"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    builder_name: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    open_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    closed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delays_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_complaint_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','reviewed','accepted','rejected')",
            name="feedback_status_enum",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    check_id: Mapped[str] = mapped_column(Text, ForeignKey("checks.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reporter_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
