"""Modelo persistente del agregado Organization."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from hys_api.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (UniqueConstraint("slug", name="uq_organizations_slug"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'America/Argentina/Buenos_Aires'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
