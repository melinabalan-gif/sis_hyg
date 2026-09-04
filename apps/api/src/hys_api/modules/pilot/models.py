"""Modelos persistentes del flujo vertical sintético del piloto."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from hys_api.db.base import Base


class Contractor(Base):
    __tablename__ = "contractors"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_contractors_organization_id_id"),
        UniqueConstraint(
            "organization_id",
            "legal_name",
            name="uq_contractors_organization_id_legal_name",
        ),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_contractors_organization_id_organizations",
        ),
        CheckConstraint("btrim(legal_name) <> ''", name="legal_name_not_blank"),
        CheckConstraint("btrim(trade) <> ''", name="trade_not_blank"),
        Index("ix_contractors_organization_id_deleted_at", "organization_id", "deleted_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    trade: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class WorksiteContractor(Base):
    __tablename__ = "worksite_contractors"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "id", name="uq_worksite_contractors_organization_id_id"
        ),
        UniqueConstraint(
            "organization_id",
            "worksite_id",
            "contractor_id",
            name="uq_worksite_contractors_org_worksite_contractor",
        ),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_worksite_contractors_organization_id_organizations",
        ),
        ForeignKeyConstraint(
            ["organization_id", "worksite_id"],
            ["worksites.organization_id", "worksites.id"],
            name="fk_worksite_contractors_org_worksite_worksites",
        ),
        ForeignKeyConstraint(
            ["organization_id", "contractor_id"],
            ["contractors.organization_id", "contractors.id"],
            name="fk_worksite_contractors_org_contractor_contractors",
        ),
        ForeignKeyConstraint(
            ["organization_id", "worksite_id", "parent_contracting_company_id"],
            [
                "worksite_contractors.organization_id",
                "worksite_contractors.worksite_id",
                "worksite_contractors.contractor_id",
            ],
            name="fk_worksite_contractors_org_worksite_parent",
        ),
        CheckConstraint("ended_on IS NULL OR ended_on > started_on", name="valid_date_range"),
        CheckConstraint(
            "participation_type IN ('PRINCIPAL', 'CONTRACTOR', 'SUBCONTRACTOR')",
            name="valid_participation_type",
        ),
        CheckConstraint(
            "(participation_type = 'PRINCIPAL' AND parent_contracting_company_id IS NULL) OR "
            "(participation_type <> 'PRINCIPAL' AND parent_contracting_company_id IS NOT NULL)",
            name="parent_required_for_non_principal",
        ),
        CheckConstraint(
            "parent_contracting_company_id IS NULL OR "
            "parent_contracting_company_id <> contractor_id",
            name="parent_cannot_be_self",
        ),
        Index(
            "ix_worksite_contractors_org_worksite_ended",
            "organization_id",
            "worksite_id",
            "ended_on",
        ),
        Index(
            "uq_worksite_contractors_one_principal",
            "organization_id",
            "worksite_id",
            unique=True,
            postgresql_where=text("participation_type = 'PRINCIPAL'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    worksite_id: Mapped[UUID] = mapped_column(nullable=False)
    contractor_id: Mapped[UUID] = mapped_column(nullable=False)
    participation_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'CONTRACTOR'")
    )
    parent_contracting_company_id: Mapped[UUID | None] = mapped_column()
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    ended_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WorksiteStage(Base):
    """A tenant-scoped temporal stage belonging to a worksite."""

    __tablename__ = "worksite_stages"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_worksite_stages_organization_id_id"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_worksite_stages_organization_id_organizations",
        ),
        ForeignKeyConstraint(
            ["organization_id", "worksite_id"],
            ["worksites.organization_id", "worksites.id"],
            name="fk_worksite_stages_org_worksite_worksites",
        ),
        CheckConstraint("ended_on IS NULL OR ended_on > started_on", name="valid_date_range"),
        CheckConstraint("btrim(code) <> ''", name="code_not_blank"),
        CheckConstraint("btrim(name) <> ''", name="name_not_blank"),
        CheckConstraint(
            "sector IS NULL OR btrim(sector) <> ''",
            name="sector_not_blank",
        ),
        CheckConstraint(
            "notes IS NULL OR btrim(notes) <> ''",
            name="notes_not_blank",
        ),
        Index(
            "ix_worksite_stages_org_worksite_started",
            "organization_id",
            "worksite_id",
            "started_on",
            "ended_on",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    worksite_id: Mapped[UUID] = mapped_column(nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    ended_on: Mapped[date | None] = mapped_column(Date)
    sector: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Person(Base):
    __tablename__ = "people"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_people_organization_id_id"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_people_organization_id_organizations",
        ),
        CheckConstraint("btrim(display_name) <> ''", name="display_name_not_blank"),
        CheckConstraint("btrim(role_label) <> ''", name="role_label_not_blank"),
        CheckConstraint(
            "profession_code IN ('LICENCIADO_HYS', 'TECNICO_HYS', 'CONTRATISTA', 'OTRA')",
            name="valid_profession_code",
        ),
        Index("ix_people_organization_id_deleted_at", "organization_id", "deleted_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role_label: Mapped[str] = mapped_column(String(120), nullable=False)
    profession_code: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'OTRA'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class PersonAssignment(Base):
    __tablename__ = "person_assignments"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_person_assignments_organization_id_id"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_person_assignments_organization_id_organizations",
        ),
        ForeignKeyConstraint(
            ["organization_id", "worksite_id"],
            ["worksites.organization_id", "worksites.id"],
            name="fk_person_assignments_org_worksite_worksites",
        ),
        ForeignKeyConstraint(
            ["organization_id", "contractor_id"],
            ["contractors.organization_id", "contractors.id"],
            name="fk_person_assignments_org_contractor_contractors",
        ),
        ForeignKeyConstraint(
            ["organization_id", "person_id"],
            ["people.organization_id", "people.id"],
            name="fk_person_assignments_org_person_people",
        ),
        CheckConstraint("ended_on IS NULL OR ended_on > started_on", name="valid_date_range"),
        Index(
            "ix_person_assignments_org_worksite_ended",
            "organization_id",
            "worksite_id",
            "ended_on",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    worksite_id: Mapped[UUID] = mapped_column(nullable=False)
    contractor_id: Mapped[UUID] = mapped_column(nullable=False)
    person_id: Mapped[UUID] = mapped_column(nullable=False)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    ended_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WorksiteFunctionalAssignment(Base):
    """A synthetic actor's explicit function and scope at one worksite."""

    __tablename__ = "worksite_functional_assignments"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "id", name="uq_worksite_functional_assignments_organization_id_id"
        ),
        UniqueConstraint(
            "organization_id",
            "worksite_id",
            "id",
            name="uq_worksite_functional_assignments_org_worksite_id",
        ),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_wfa_organization_id_organizations",
        ),
        ForeignKeyConstraint(
            ["organization_id", "worksite_id"],
            ["worksites.organization_id", "worksites.id"],
            name="fk_worksite_functional_assignments_org_worksite_worksites",
        ),
        ForeignKeyConstraint(
            ["organization_id", "person_id"],
            ["people.organization_id", "people.id"],
            name="fk_worksite_functional_assignments_org_person_people",
        ),
        ForeignKeyConstraint(
            ["organization_id", "represented_contractor_id"],
            ["contractors.organization_id", "contractors.id"],
            name="fk_worksite_functional_assignments_org_contractor_contractors",
        ),
        CheckConstraint(
            "function_code IN ("
            "'RESPONSABLE_HYS_PROYECTO', 'AUDITOR_DELEGADO_PROYECTO', "
            "'RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL', "
            "'TECNICO_HYS_CONTRATISTA_PRINCIPAL')",
            name="valid_function_code",
        ),
        CheckConstraint(
            "permission_scope IN ('WORKSITE', 'ORGANIZATION')",
            name="valid_permission_scope",
        ),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="valid_date_range"),
        Index(
            "ix_worksite_functional_assignments_org_worksite_actor_active",
            "organization_id",
            "worksite_id",
            "actor_id",
            "valid_to",
        ),
        Index(
            "ix_worksite_functional_assignments_org_worksite_function",
            "organization_id",
            "worksite_id",
            "function_code",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    worksite_id: Mapped[UUID] = mapped_column(nullable=False)
    actor_id: Mapped[UUID] = mapped_column(nullable=False)
    person_id: Mapped[UUID | None] = mapped_column()
    function_code: Mapped[str] = mapped_column(String(64), nullable=False)
    represented_contractor_id: Mapped[UUID | None] = mapped_column()
    permission_scope: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'WORKSITE'")
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Machine(Base):
    __tablename__ = "machines"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_machines_organization_id_id"),
        UniqueConstraint(
            "organization_id",
            "internal_code",
            name="uq_machines_organization_id_internal_code",
        ),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_machines_organization_id_organizations",
        ),
        CheckConstraint(
            "status IN ('OPERATIVA', 'CON_OBSERVACIONES', 'FUERA_DE_SERVICIO')",
            name="valid_status",
        ),
        CheckConstraint("btrim(internal_code) <> ''", name="internal_code_not_blank"),
        CheckConstraint("btrim(description) <> ''", name="description_not_blank"),
        Index("ix_machines_organization_id_status", "organization_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    internal_code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'OPERATIVA'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class MachineWorksiteAssignment(Base):
    __tablename__ = "machine_worksite_assignments"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_machine_worksite_assignments_organization_id_id",
        ),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_machine_worksite_assignments_organization_id_organizations",
        ),
        ForeignKeyConstraint(
            ["organization_id", "worksite_id"],
            ["worksites.organization_id", "worksites.id"],
            name="fk_machine_worksite_assignments_org_worksite_worksites",
        ),
        ForeignKeyConstraint(
            ["organization_id", "contractor_id"],
            ["contractors.organization_id", "contractors.id"],
            name="fk_machine_worksite_assignments_org_contractor_contractors",
        ),
        ForeignKeyConstraint(
            ["organization_id", "machine_id"],
            ["machines.organization_id", "machines.id"],
            name="fk_machine_worksite_assignments_org_machine_machines",
        ),
        CheckConstraint("ended_on IS NULL OR ended_on > started_on", name="valid_date_range"),
        Index(
            "ix_machine_worksite_assignments_org_worksite_ended",
            "organization_id",
            "worksite_id",
            "ended_on",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    worksite_id: Mapped[UUID] = mapped_column(nullable=False)
    contractor_id: Mapped[UUID | None] = mapped_column()
    machine_id: Mapped[UUID] = mapped_column(nullable=False)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    ended_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MachineInspection(Base):
    __tablename__ = "machine_inspections"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_machine_inspections_organization_id_id"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_machine_inspections_organization_id_organizations",
        ),
        ForeignKeyConstraint(
            ["organization_id", "machine_id"],
            ["machines.organization_id", "machines.id"],
            name="fk_machine_inspections_org_machine_machines",
        ),
        ForeignKeyConstraint(
            ["organization_id", "worksite_id"],
            ["worksites.organization_id", "worksites.id"],
            name="fk_machine_inspections_org_worksite_worksites",
        ),
        CheckConstraint(
            "resulting_status IN ('OPERATIVA', 'CON_OBSERVACIONES', 'FUERA_DE_SERVICIO')",
            name="valid_resulting_status",
        ),
        CheckConstraint("btrim(reason) <> ''", name="reason_not_blank"),
        Index(
            "ix_machine_inspections_org_worksite_inspected",
            "organization_id",
            "worksite_id",
            "inspected_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    machine_id: Mapped[UUID] = mapped_column(nullable=False)
    worksite_id: Mapped[UUID] = mapped_column(nullable=False)
    resulting_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(nullable=False)
    inspected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_documents_organization_id_id"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_documents_organization_id_organizations",
        ),
        CheckConstraint(
            "review_status IN ('PENDIENTE', 'APROBADO', 'RECHAZADO')",
            name="valid_review_status",
        ),
        CheckConstraint(
            "expires_on IS NULL OR valid_from IS NULL OR expires_on >= valid_from",
            name="valid_date_range",
        ),
        CheckConstraint("btrim(title) <> ''", name="title_not_blank"),
        CheckConstraint("btrim(document_type) <> ''", name="document_type_not_blank"),
        Index(
            "ix_documents_org_review_expires",
            "organization_id",
            "review_status",
            "expires_on",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'PENDIENTE'")
    )
    valid_from: Mapped[date | None] = mapped_column(Date)
    expires_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class DocumentVersion(Base):
    """An immutable metadata snapshot for a document."""

    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_document_versions_organization_id_id"),
        UniqueConstraint(
            "organization_id",
            "document_id",
            "version_number",
            name="uq_document_versions_org_document_version",
        ),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_document_versions_organization_id_organizations",
        ),
        ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["documents.organization_id", "documents.id"],
            name="fk_document_versions_org_document_documents",
        ),
        CheckConstraint(
            "review_status IN ('PENDIENTE', 'APROBADO', 'RECHAZADO')",
            name="valid_review_status",
        ),
        CheckConstraint(
            "expires_on IS NULL OR valid_from IS NULL OR expires_on >= valid_from",
            name="valid_date_range",
        ),
        CheckConstraint("version_number > 0", name="positive_version_number"),
        CheckConstraint("btrim(title) <> ''", name="title_not_blank"),
        CheckConstraint("btrim(document_type) <> ''", name="document_type_not_blank"),
        Index(
            "ix_document_versions_org_document_version",
            "organization_id",
            "document_id",
            "version_number",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date)
    expires_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WorksiteDocument(Base):
    __tablename__ = "worksite_documents"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_worksite_documents_organization_id_id"),
        UniqueConstraint("document_id", name="uq_worksite_documents_document_id"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_worksite_documents_organization_id_organizations",
        ),
        ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["documents.organization_id", "documents.id"],
            name="fk_worksite_documents_org_document_documents",
        ),
        ForeignKeyConstraint(
            ["organization_id", "worksite_id"],
            ["worksites.organization_id", "worksites.id"],
            name="fk_worksite_documents_org_worksite_worksites",
        ),
        Index("ix_worksite_documents_org_worksite", "organization_id", "worksite_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    worksite_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ContractorDocument(Base):
    __tablename__ = "contractor_documents"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "id", name="uq_contractor_documents_organization_id_id"
        ),
        UniqueConstraint("document_id", name="uq_contractor_documents_document_id"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_contractor_documents_organization_id_organizations",
        ),
        ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["documents.organization_id", "documents.id"],
            name="fk_contractor_documents_org_document_documents",
        ),
        ForeignKeyConstraint(
            ["organization_id", "contractor_id"],
            ["contractors.organization_id", "contractors.id"],
            name="fk_contractor_documents_org_contractor_contractors",
        ),
        Index("ix_contractor_documents_org_contractor", "organization_id", "contractor_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    contractor_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PersonDocument(Base):
    __tablename__ = "person_documents"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_person_documents_organization_id_id"),
        UniqueConstraint("document_id", name="uq_person_documents_document_id"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_person_documents_organization_id_organizations",
        ),
        ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["documents.organization_id", "documents.id"],
            name="fk_person_documents_org_document_documents",
        ),
        ForeignKeyConstraint(
            ["organization_id", "person_id"],
            ["people.organization_id", "people.id"],
            name="fk_person_documents_org_person_people",
        ),
        Index("ix_person_documents_org_person", "organization_id", "person_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    person_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MachineDocument(Base):
    __tablename__ = "machine_documents"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_machine_documents_organization_id_id"),
        UniqueConstraint("document_id", name="uq_machine_documents_document_id"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_machine_documents_organization_id_organizations",
        ),
        ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["documents.organization_id", "documents.id"],
            name="fk_machine_documents_org_document_documents",
        ),
        ForeignKeyConstraint(
            ["organization_id", "machine_id"],
            ["machines.organization_id", "machines.id"],
            name="fk_machine_documents_org_machine_machines",
        ),
        Index("ix_machine_documents_org_machine", "organization_id", "machine_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    machine_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ControlCatalogVersion(Base):
    __tablename__ = "control_catalog_versions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "id", name="uq_control_catalog_versions_organization_id_id"
        ),
        UniqueConstraint(
            "organization_id",
            "code",
            "version_number",
            name="uq_control_catalog_versions_org_code_version",
        ),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_control_catalog_versions_organization_id_organizations",
        ),
        CheckConstraint("btrim(code) <> ''", name="code_not_blank"),
        CheckConstraint("btrim(title) <> ''", name="title_not_blank"),
        CheckConstraint("version_number > 0", name="positive_version_number"),
        Index("ix_control_catalog_versions_org_code", "organization_id", "code"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SeverityCatalogVersion(Base):
    __tablename__ = "severity_catalog_versions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "id", name="uq_severity_catalog_versions_organization_id_id"
        ),
        UniqueConstraint(
            "organization_id",
            "code",
            "version_number",
            name="uq_severity_catalog_versions_org_code_version",
        ),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_severity_catalog_versions_organization_id_organizations",
        ),
        CheckConstraint("code IN ('BAJA', 'MEDIA', 'ALTA', 'CRITICA')", name="valid_code"),
        CheckConstraint("btrim(label) <> ''", name="label_not_blank"),
        CheckConstraint("sort_order >= 0", name="nonnegative_sort_order"),
        CheckConstraint("default_due_days >= 0", name="nonnegative_default_due_days"),
        CheckConstraint("version_number > 0", name="positive_version_number"),
        Index("ix_severity_catalog_versions_org_code", "organization_id", "code"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    default_due_days: Mapped[int] = mapped_column(Integer, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Audit(Base):
    __tablename__ = "audits"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_audits_organization_id_id"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_audits_organization_id_organizations",
        ),
        ForeignKeyConstraint(
            ["organization_id", "worksite_id"],
            ["worksites.organization_id", "worksites.id"],
            name="fk_audits_org_worksite_worksites",
        ),
        ForeignKeyConstraint(
            ["organization_id", "control_catalog_version_id"],
            ["control_catalog_versions.organization_id", "control_catalog_versions.id"],
            name="fk_audits_org_control_catalog_control_catalog_versions",
        ),
        ForeignKeyConstraint(
            ["organization_id", "worksite_id", "auditor_assignment_id"],
            [
                "worksite_functional_assignments.organization_id",
                "worksite_functional_assignments.worksite_id",
                "worksite_functional_assignments.id",
            ],
            name="fk_audits_org_worksite_auditor_assignment",
        ),
        ForeignKeyConstraint(
            ["organization_id", "associated_professional_person_id"],
            ["people.organization_id", "people.id"],
            name="fk_audits_org_professional_person_people",
        ),
        CheckConstraint("status IN ('EN_CURSO', 'FINALIZADA')", name="valid_status"),
        CheckConstraint(
            "(status = 'EN_CURSO' AND finalized_at IS NULL) OR "
            "(status = 'FINALIZADA' AND finalized_at IS NOT NULL)",
            name="status_matches_finalized_at",
        ),
        Index("ix_audits_org_worksite_status", "organization_id", "worksite_id", "status"),
        Index(
            "ix_audits_org_worksite_auditor_assignment",
            "organization_id",
            "worksite_id",
            "auditor_assignment_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    worksite_id: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'EN_CURSO'")
    )
    author_actor_id: Mapped[UUID] = mapped_column(nullable=False)
    editor_actor_id: Mapped[UUID] = mapped_column(nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    control_catalog_version_id: Mapped[UUID] = mapped_column(nullable=False)
    auditor_actor_id: Mapped[UUID | None] = mapped_column()
    auditor_assignment_id: Mapped[UUID | None] = mapped_column()
    associated_professional_person_id: Mapped[UUID | None] = mapped_column()
    audit_date: Mapped[date | None] = mapped_column(Date)


class AuditControl(Base):
    __tablename__ = "audit_controls"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_audit_controls_organization_id_id"),
        UniqueConstraint(
            "organization_id",
            "audit_id",
            "catalog_code",
            name="uq_audit_controls_org_audit_catalog_code",
        ),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_audit_controls_organization_id_organizations",
        ),
        ForeignKeyConstraint(
            ["organization_id", "audit_id"],
            ["audits.organization_id", "audits.id"],
            name="fk_audit_controls_org_audit_audits",
        ),
        CheckConstraint(
            "result IN ('CUMPLE', 'NO_CUMPLE', 'NO_APLICA', 'NO_VERIFICADO')",
            name="valid_result",
        ),
        CheckConstraint(
            "result NOT IN ('NO_APLICA', 'NO_VERIFICADO') OR NULLIF(btrim(reason), '') IS NOT NULL",
            name="reason_required_for_unresolved_result",
        ),
        CheckConstraint("btrim(catalog_code) <> ''", name="catalog_code_not_blank"),
        CheckConstraint("btrim(catalog_title) <> ''", name="catalog_title_not_blank"),
        Index("ix_audit_controls_org_audit_result", "organization_id", "audit_id", "result"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    audit_id: Mapped[UUID] = mapped_column(nullable=False)
    catalog_code: Mapped[str] = mapped_column(String(64), nullable=False)
    catalog_title: Mapped[str] = mapped_column(String(200), nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    recorded_by_actor_id: Mapped[UUID] = mapped_column(nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_findings_organization_id_id"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_findings_organization_id_organizations",
        ),
        ForeignKeyConstraint(
            ["organization_id", "worksite_id"],
            ["worksites.organization_id", "worksites.id"],
            name="fk_findings_org_worksite_worksites",
        ),
        ForeignKeyConstraint(
            ["organization_id", "audit_id"],
            ["audits.organization_id", "audits.id"],
            name="fk_findings_org_audit_audits",
        ),
        ForeignKeyConstraint(
            ["organization_id", "severity_catalog_version_id"],
            ["severity_catalog_versions.organization_id", "severity_catalog_versions.id"],
            name="fk_findings_org_severity_severity_catalog_versions",
        ),
        CheckConstraint(
            "status IN ('ABIERTO', 'EN_CORRECCION', 'PENDIENTE_VERIFICACION', 'CERRADO')",
            name="valid_status",
        ),
        CheckConstraint(
            "severity_code IN ('BAJA', 'MEDIA', 'ALTA', 'CRITICA')",
            name="valid_severity_code",
        ),
        CheckConstraint(
            "(status = 'CERRADO' AND closed_at IS NOT NULL) OR "
            "(status <> 'CERRADO' AND closed_at IS NULL)",
            name="status_matches_closed_at",
        ),
        CheckConstraint("btrim(title) <> ''", name="title_not_blank"),
        CheckConstraint("btrim(description) <> ''", name="description_not_blank"),
        CheckConstraint("btrim(severity_label) <> ''", name="severity_label_not_blank"),
        Index("ix_findings_org_worksite_status", "organization_id", "worksite_id", "status"),
        Index("ix_findings_org_status_due_at", "organization_id", "status", "due_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    worksite_id: Mapped[UUID] = mapped_column(nullable=False)
    audit_id: Mapped[UUID] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'ABIERTO'")
    )
    severity_catalog_version_id: Mapped[UUID] = mapped_column(nullable=False)
    severity_code: Mapped[str] = mapped_column(String(16), nullable=False)
    severity_label: Mapped[str] = mapped_column(String(100), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_actor_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class FindingControl(Base):
    __tablename__ = "finding_controls"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_finding_controls_organization_id_id"),
        UniqueConstraint("audit_control_id", name="uq_finding_controls_audit_control_id"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_finding_controls_organization_id_organizations",
        ),
        ForeignKeyConstraint(
            ["organization_id", "finding_id"],
            ["findings.organization_id", "findings.id"],
            name="fk_finding_controls_org_finding_findings",
        ),
        ForeignKeyConstraint(
            ["organization_id", "audit_control_id"],
            ["audit_controls.organization_id", "audit_controls.id"],
            name="fk_finding_controls_org_audit_control_audit_controls",
        ),
        Index("ix_finding_controls_org_finding", "organization_id", "finding_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    finding_id: Mapped[UUID] = mapped_column(nullable=False)
    audit_control_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Correction(Base):
    __tablename__ = "corrections"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_corrections_organization_id_id"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_corrections_organization_id_organizations",
        ),
        ForeignKeyConstraint(
            ["organization_id", "finding_id"],
            ["findings.organization_id", "findings.id"],
            name="fk_corrections_org_finding_findings",
        ),
        CheckConstraint("btrim(description) <> ''", name="description_not_blank"),
        CheckConstraint("btrim(evidence_note) <> ''", name="evidence_note_not_blank"),
        Index("ix_corrections_org_finding_created", "organization_id", "finding_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    finding_id: Mapped[UUID] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_note: Mapped[str] = mapped_column(Text, nullable=False)
    authored_by_actor_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Verification(Base):
    __tablename__ = "verifications"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_verifications_organization_id_id"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_verifications_organization_id_organizations",
        ),
        ForeignKeyConstraint(
            ["organization_id", "finding_id"],
            ["findings.organization_id", "findings.id"],
            name="fk_verifications_org_finding_findings",
        ),
        CheckConstraint("decision IN ('ACEPTADA', 'RECHAZADA')", name="valid_decision"),
        CheckConstraint(
            "decision <> 'RECHAZADA' OR btrim(notes) <> ''",
            name="notes_required_for_rejection",
        ),
        Index(
            "ix_verifications_org_finding_created",
            "organization_id",
            "finding_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    finding_id: Mapped[UUID] = mapped_column(nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    verified_by_actor_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FindingEvent(Base):
    __tablename__ = "finding_events"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_finding_events_organization_id_id"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_finding_events_organization_id_organizations",
        ),
        ForeignKeyConstraint(
            ["organization_id", "finding_id"],
            ["findings.organization_id", "findings.id"],
            name="fk_finding_events_org_finding_findings",
        ),
        CheckConstraint(
            "from_status IS NULL OR from_status IN "
            "('ABIERTO', 'EN_CORRECCION', 'PENDIENTE_VERIFICACION', 'CERRADO')",
            name="valid_from_status",
        ),
        CheckConstraint(
            "to_status IN ('ABIERTO', 'EN_CORRECCION', 'PENDIENTE_VERIFICACION', 'CERRADO')",
            name="valid_to_status",
        ),
        CheckConstraint("btrim(event_type) <> ''", name="event_type_not_blank"),
        Index(
            "ix_finding_events_org_finding_created",
            "organization_id",
            "finding_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    finding_id: Mapped[UUID] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = [
    "Audit",
    "AuditControl",
    "Contractor",
    "ContractorDocument",
    "ControlCatalogVersion",
    "Correction",
    "Document",
    "Finding",
    "FindingControl",
    "FindingEvent",
    "Machine",
    "MachineDocument",
    "MachineInspection",
    "MachineWorksiteAssignment",
    "Person",
    "PersonAssignment",
    "PersonDocument",
    "SeverityCatalogVersion",
    "Verification",
    "WorksiteContractor",
    "WorksiteDocument",
    "WorksiteFunctionalAssignment",
]
