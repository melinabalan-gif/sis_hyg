"""Modelo persistente del agregado Worksite."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from hys_api.db.base import Base


class Worksite(Base):
    __tablename__ = "worksites"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_worksites_organization_id_id"),
        UniqueConstraint("organization_id", "code", name="uq_worksites_organization_id_code"),
        CheckConstraint(
            "status IN ('ACTIVE', 'ARCHIVED')",
            name="valid_status",
        ),
        Index("ix_worksites_organization_id_status", "organization_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", name="fk_worksites_organization_id_organizations"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'ACTIVE'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
