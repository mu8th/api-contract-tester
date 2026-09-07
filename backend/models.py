"""SQLAlchemy ORM models for API Contract Tester."""

from __future__ import annotations

import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base class for all models."""


def _utcnow() -> datetime.datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.datetime.now(datetime.UTC)


class Spec(Base):
    """A stored OpenAPI specification document."""

    __tablename__ = "specs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class Test(Base):
    """One contract enforcement run against a live endpoint."""

    __tablename__ = "tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    spec_id: Mapped[int] = mapped_column(ForeignKey("specs.id"), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[bool] = mapped_column(Boolean, nullable=False)
    severity_score: Mapped[float | None] = mapped_column(Float, nullable=True)


class Result(Base):
    """One schema drift finding from a test run."""

    __tablename__ = "results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id"), nullable=False)
    field_name: Mapped[str] = mapped_column(String(512), nullable=False)
    expected_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actual_type: Mapped[str] = mapped_column(String(64), nullable=False)
    breaking_change: Mapped[bool] = mapped_column(Boolean, nullable=False)
