"""Casos de uso transaccionales del primer flujo vertical sintético."""

from collections.abc import Collection
from datetime import UTC, date, datetime, timedelta, timezone, tzinfo
from functools import lru_cache
from typing import Annotated, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends
from sqlalchemy import and_, exists, literal, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from hys_api.api.dependencies import (
    PILOT_ACTORS,
    PILOT_ORGANIZATION_ID,
    PilotRequestContext,
    PilotRole,
    get_pilot_context,
    require_pilot_role,
)
from hys_api.core.errors import ProblemException
from hys_api.modules.pilot.models import (
    Audit,
    AuditControl,
    Contractor,
    ContractorDocument,
    ControlCatalogVersion,
    Correction,
    Document,
    DocumentReview,
    DocumentVersion,
    Finding,
    FindingControl,
    FindingEvent,
    Machine,
    MachineDocument,
    MachineInspection,
    MachineInspectionValidation,
    MachineWorksiteAssignment,
    Person,
    PersonAssignment,
    PersonDocument,
    PersonVerification,
    SeverityCatalogVersion,
    Verification,
    WorksiteContractor,
    WorksiteDocument,
    WorksiteFunctionalAssignment,
    WorksiteStage,
    WorksiteStageEvent,
)
from hys_api.modules.pilot.schemas import (
    AuditControlCreate,
    AuditControlMutationResponse,
    AuditControlView,
    AuditStartCreate,
    AuditView,
    ContractorCreate,
    ContractorParticipationType,
    ContractorView,
    CorrectionCreate,
    CorrectionView,
    DocumentCreate,
    DocumentReviewCreate,
    DocumentReviewView,
    DocumentVersionCreate,
    DocumentVersionView,
    DocumentView,
    FindingEventView,
    FindingTimeline,
    FindingView,
    MachineCreate,
    MachineInspectionCreate,
    MachineInspectionValidationCreate,
    MachineInspectionView,
    MachineView,
    PersonCreate,
    PersonVerificationCreate,
    PersonView,
    SubjectKind,
    UnregisteredPersonFindingCreate,
    VerificationCreate,
    VerificationDecision,
    VerificationView,
    WorksiteCreate,
    WorksiteDetail,
    WorksiteFunctionalAssignmentCreate,
    WorksiteFunctionalAssignmentView,
    WorksiteStageCreate,
    WorksiteStageEventView,
    WorksiteStageUpdate,
    WorksiteStageView,
    WorksiteSummary,
    derive_document_status,
    derive_worksite_metrics,
)
from hys_api.modules.worksites.models import Worksite

_PROJECT_FUNCTIONS = frozenset({"RESPONSABLE_HYS_PROYECTO", "AUDITOR"})
_CONTRACTOR_FUNCTIONS = frozenset(
    {
        "RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL",
        "TECNICO_HYS_CONTRATISTA_PRINCIPAL",
        "RESPONSABLE_HYS_CONTRATISTA",
        "TECNICO_HYS_CONTRATISTA",
    }
)
_PRINCIPAL_CONTRACTOR_FUNCTIONS = frozenset(
    {"RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL", "TECNICO_HYS_CONTRATISTA_PRINCIPAL"}
)
_OTHER_CONTRACTOR_FUNCTIONS = frozenset({"RESPONSABLE_HYS_CONTRATISTA", "TECNICO_HYS_CONTRATISTA"})
_ALL_FUNCTIONS = _PROJECT_FUNCTIONS | _CONTRACTOR_FUNCTIONS
_RESPONSIBLE_FUNCTIONS = frozenset(
    {"RESPONSABLE_HYS_PROYECTO", "RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL"}
)
_CONTRACTOR_ACTOR_KEYS = frozenset(
    {
        "tecnico",
        "responsable-suplente",
        "licenciado-contratista-principal",
        "tecnico-contratista",
        "licenciado-contratista",
    }
)
_DOCUMENT_REVIEW_FUNCTIONS = frozenset(
    {
        "AUDITOR",
        "RESPONSABLE_HYS_PROYECTO",
        "RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL",
    }
)


@lru_cache(maxsize=1)
def _argentina_timezone() -> tzinfo:
    """Usa IANA cuando está disponible y el offset vigente como fallback Windows."""

    try:
        return ZoneInfo("America/Argentina/Buenos_Aires")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=-3), name="America/Argentina/Buenos_Aires")


def _today_in_argentina() -> date:
    return datetime.now(_argentina_timezone()).date()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _not_found() -> ProblemException:
    return ProblemException(
        status=404,
        code="pilot_resource_not_found",
        title="Recurso no encontrado",
        detail="El recurso no existe o no está visible para el actor del piloto.",
    )


def _conflict(code: str, detail: str) -> ProblemException:
    return ProblemException(
        status=409,
        code=code,
        title="La operación entra en conflicto con el estado actual",
        detail=detail,
    )


def _unprocessable(code: str, detail: str) -> ProblemException:
    return ProblemException(
        status=422,
        code=code,
        title="La solicitud no es válida",
        detail=detail,
    )


class PilotService:
    """Orquesta los módulos del corte piloto dentro de una única UoW."""

    def __init__(self, context: PilotRequestContext) -> None:
        self.context = context
        self.session: AsyncSession = context.session

    async def list_worksites(self) -> list[WorksiteSummary]:
        today = _today_in_argentina()
        allowed_scope = self._allowed_assignment_scope()
        organization_reader = self.context.actor.role is PilotRole.CONTRATISTA
        rows = await self.session.scalars(
            select(Worksite)
            .where(
                Worksite.organization_id == PILOT_ORGANIZATION_ID,
                Worksite.deleted_at.is_(None),
                or_(
                    Worksite.created_by_actor_id == self.context.actor.id,
                    literal(organization_reader),
                    exists(
                        select(WorksiteFunctionalAssignment.id).where(
                            WorksiteFunctionalAssignment.organization_id
                            == Worksite.organization_id,
                            WorksiteFunctionalAssignment.worksite_id == Worksite.id,
                            WorksiteFunctionalAssignment.actor_id == self.context.actor.id,
                            allowed_scope,
                            WorksiteFunctionalAssignment.valid_from <= today,
                            or_(
                                WorksiteFunctionalAssignment.valid_to.is_(None),
                                WorksiteFunctionalAssignment.valid_to > today,
                            ),
                        )
                    ),
                ),
            )
            .order_by(Worksite.code, Worksite.id)
        )
        return [self._worksite_summary(row) for row in rows]

    async def create_worksite(self, payload: WorksiteCreate) -> WorksiteSummary:
        self._require_resource_write()
        if self.context.actor.key in {"responsable-suplente", "licenciado-contratista-principal"}:
            raise ProblemException(
                status=403,
                code="pilot_project_delegation_required",
                title="Delegación de proyecto requerida",
                detail="El Licenciado H&S de una contratista no puede crear obras.",
            )
        worksite = Worksite(
            organization_id=PILOT_ORGANIZATION_ID,
            code=payload.code,
            name=payload.name,
            country=payload.country,
            province=payload.province,
            municipality=payload.municipality,
            jurisdiction=payload.jurisdiction
            or "/".join(
                value
                for value in (payload.country, payload.province, payload.municipality)
                if value
            ),
            created_by_actor_id=self.context.actor.id,
        )
        self.session.add(worksite)
        await self._flush_or_conflict(
            "duplicate_worksite_code",
            "Ya existe una obra sintética con ese código.",
        )
        await self.session.refresh(worksite)
        return self._worksite_summary(worksite)

    async def get_worksite_detail(self, worksite_id: UUID) -> WorksiteDetail:
        worksite = await self._get_worksite(worksite_id)
        await self._require_read_access(worksite_id)
        contractors = await self._contractors_for_worksite(worksite_id)
        functional_assignments = await self._functional_assignments_for_worksite(worksite_id)
        people = await self._people_for_worksite(worksite_id)
        documents = await self._documents_for_worksite(worksite)
        machines = await self._machines_for_worksite(worksite_id)
        stages = await self._stages_for_worksite(worksite_id)
        audits = await self._audits_for_worksite(worksite_id)
        findings = await self._findings_for_worksite(worksite_id)
        contractor_scope = await self._contractor_scope_ids(worksite_id)
        if contractor_scope:
            visible_contractor_ids = {
                item.id for item in contractors if item.id in contractor_scope
            }
            visible_people = [
                item for item in people if item.contractor_id in visible_contractor_ids
            ]
            visible_person_ids = {item.id for item in visible_people}
            visible_machines = [
                item for item in machines if item.contractor_id in visible_contractor_ids
            ]
            visible_machine_ids = {item.id for item in visible_machines}
            contractors = [item for item in contractors if item.id in visible_contractor_ids]
            people = visible_people
            machines = visible_machines
            documents = [
                item
                for item in documents
                if (item.subject_kind is SubjectKind.WORKSITE)
                or (
                    item.subject_kind is SubjectKind.CONTRACTOR
                    and item.subject_id in visible_contractor_ids
                )
                or (
                    item.subject_kind is SubjectKind.PERSON
                    and item.subject_id in visible_person_ids
                )
                or (
                    item.subject_kind is SubjectKind.MACHINE
                    and item.subject_id in visible_machine_ids
                )
            ]
            functional_assignments = [
                item
                for item in functional_assignments
                if item.represented_contractor_id in visible_contractor_ids
            ]
            findings = [
                item for item in findings if item.affected_contractor_id in visible_contractor_ids
            ]
        metrics = derive_worksite_metrics(
            documents,
            findings,
            machines,
            audits,
            now=_utc_now(),
        )
        return WorksiteDetail.model_validate(
            {
                **self._worksite_summary(worksite).model_dump(),
                "contractors": contractors,
                "functional_assignments": functional_assignments,
                "people": people,
                "documents": documents,
                "machines": machines,
                "stages": stages,
                "audits": audits,
                "findings": findings,
                "metrics": metrics,
            }
        )

    async def create_worksite_stage(
        self,
        worksite_id: UUID,
        payload: WorksiteStageCreate,
    ) -> WorksiteStageView:
        self._require_resource_write()
        await self._get_active_worksite(worksite_id)
        await self._authorize_worksite_write_scope(worksite_id)
        stage = WorksiteStage(
            organization_id=PILOT_ORGANIZATION_ID,
            worksite_id=worksite_id,
            code=payload.code,
            name=payload.name,
            started_on=payload.started_on,
            ended_on=payload.ended_on,
            sector=payload.sector,
            notes=payload.notes,
        )
        self.session.add(stage)
        await self._flush_or_conflict(
            "worksite_stage_conflict",
            "No se pudo crear la etapa sintética de la obra.",
        )
        await self.session.refresh(stage)
        self.session.add(
            WorksiteStageEvent(
                organization_id=PILOT_ORGANIZATION_ID,
                stage_id=stage.id,
                actor_id=self.context.actor.id,
                event_type="CREATED",
                detail="Etapa creada en la línea temporal de la obra.",
            )
        )
        await self.session.flush()
        return await self._worksite_stage_view_with_history(stage)

    async def update_worksite_stage(
        self,
        worksite_id: UUID,
        stage_id: UUID,
        payload: WorksiteStageUpdate,
    ) -> WorksiteStageView:
        self._require_resource_write()
        await self._get_active_worksite(worksite_id)
        await self._authorize_worksite_write_scope(worksite_id)
        stage = await self.session.scalar(
            select(WorksiteStage)
            .where(
                WorksiteStage.organization_id == PILOT_ORGANIZATION_ID,
                WorksiteStage.worksite_id == worksite_id,
                WorksiteStage.id == stage_id,
            )
            .with_for_update()
        )
        if stage is None:
            raise _not_found()
        if payload.ended_on is not None and payload.ended_on <= stage.started_on:
            raise _unprocessable(
                "invalid_stage_interval",
                "La fecha de fin de la etapa debe ser posterior a la fecha de inicio.",
            )
        if (
            payload.status == "CERRADA"
            and payload.ended_on is None
            and stage.ended_on is None
            and _today_in_argentina() <= stage.started_on
        ):
            raise _unprocessable(
                "invalid_stage_interval",
                "Una etapa no puede cerrarse antes de su fecha de inicio.",
            )
        changes: list[str] = []
        for field in ("name", "ended_on", "sector", "notes"):
            value = getattr(payload, field)
            if value is not None:
                setattr(stage, field, value)
                changes.append(field)
        if payload.status == "CERRADA" and stage.ended_on is None:
            stage.ended_on = _today_in_argentina()
            changes.append("status")
        elif payload.status is not None:
            changes.append("status")
        if payload.status is not None:
            stage.status = payload.status
        if changes:
            self.session.add(
                WorksiteStageEvent(
                    organization_id=PILOT_ORGANIZATION_ID,
                    stage_id=stage.id,
                    actor_id=self.context.actor.id,
                    event_type="UPDATED",
                    detail=f"Campos modificados: {', '.join(changes)}.",
                )
            )
        await self.session.flush()
        return await self._worksite_stage_view_with_history(stage)

    async def create_contractor(
        self,
        worksite_id: UUID,
        payload: ContractorCreate,
    ) -> ContractorView:
        self._require_resource_write()
        await self._get_active_worksite(worksite_id)
        participation_type = payload.participation_type
        scope_ids = await self._contractor_scope_ids(worksite_id)
        if participation_type is None:
            principal_id = await self.session.scalar(
                select(WorksiteContractor.contractor_id)
                .where(
                    WorksiteContractor.organization_id == PILOT_ORGANIZATION_ID,
                    WorksiteContractor.worksite_id == worksite_id,
                    WorksiteContractor.participation_type == "PRINCIPAL",
                )
                .limit(1)
            )
            participation_type = (
                ContractorParticipationType.CONTRACTOR
                if principal_id is not None
                else ContractorParticipationType.PRINCIPAL
            )
        parent_id = payload.parent_contracting_company_id
        if participation_type is not ContractorParticipationType.PRINCIPAL and parent_id is None:
            if len(scope_ids) == 1:
                parent_id = next(iter(scope_ids))
        if participation_type is ContractorParticipationType.PRINCIPAL:
            if scope_ids:
                raise ProblemException(
                    status=403,
                    code="pilot_contractor_scope_denied",
                    title="Alcance de contratista insuficiente",
                    detail=(
                        "Un profesional de contratista sólo puede registrar empresas "
                        "dependientes de la empresa que representa."
                    ),
                )
            if parent_id is not None:
                raise _unprocessable(
                    "principal_parent_forbidden",
                    "El contratista principal no puede depender de otra empresa.",
                )
        else:
            if parent_id is None:
                raise _unprocessable(
                    "contractor_parent_required",
                    "Un contratista no principal debe indicar su empresa contratante.",
                )
            await self._authorize_worksite_write_scope(
                worksite_id, contractor_ids={parent_id}, require_contractor_target=True
            )
            parent = await self.session.scalar(
                select(WorksiteContractor).where(
                    WorksiteContractor.organization_id == PILOT_ORGANIZATION_ID,
                    WorksiteContractor.worksite_id == worksite_id,
                    WorksiteContractor.contractor_id == parent_id,
                )
            )
            if parent is None:
                raise _not_found()
        contractor = Contractor(
            organization_id=PILOT_ORGANIZATION_ID,
            legal_name=payload.legal_name,
            trade=payload.trade,
        )
        self.session.add(contractor)
        await self._flush_or_conflict(
            "duplicate_contractor",
            "El contratista sintético ya existe en la organización.",
        )
        assignment = WorksiteContractor(
            organization_id=PILOT_ORGANIZATION_ID,
            worksite_id=worksite_id,
            contractor_id=contractor.id,
            participation_type=participation_type.value,
            parent_contracting_company_id=parent_id,
            started_on=payload.started_on or _today_in_argentina(),
            ended_on=payload.ended_on,
        )
        self.session.add(assignment)
        await self._flush_or_conflict(
            "contractor_assignment_conflict",
            "No se pudo asignar el contratista sintético a la obra.",
        )
        await self.session.refresh(contractor)
        await self.session.refresh(assignment)
        return self._contractor_view(contractor, assignment)

    async def create_person(self, worksite_id: UUID, payload: PersonCreate) -> PersonView:
        self._require_resource_write()
        worksite = await self._get_active_worksite(worksite_id)
        started_on = payload.started_on or _today_in_argentina()
        if payload.contractor_id is not None:
            await self._authorize_worksite_write_scope(
                worksite_id, contractor_ids={payload.contractor_id}, require_contractor_target=True
            )
            await self._get_contractor_for_worksite(
                worksite_id, payload.contractor_id, on_date=started_on
            )
        elif worksite.created_by_actor_id != self.context.actor.id:
            await self._require_current_function(worksite_id, _PROJECT_FUNCTIONS)
        person = Person(
            organization_id=PILOT_ORGANIZATION_ID,
            display_name=payload.display_name,
            role_label=payload.role_label,
            profession_code=payload.profession_code.value,
        )
        self.session.add(person)
        await self.session.flush()
        assignment = PersonAssignment(
            organization_id=PILOT_ORGANIZATION_ID,
            worksite_id=worksite_id,
            contractor_id=payload.contractor_id,
            person_id=person.id,
            started_on=started_on,
            ended_on=payload.ended_on,
        )
        self.session.add(assignment)
        await self._flush_or_conflict(
            "person_assignment_conflict",
            "No se pudo crear la persona y su asignación sintética.",
        )
        await self.session.refresh(person)
        await self.session.refresh(assignment)
        return self._person_view(person, assignment)

    async def verify_person(
        self,
        worksite_id: UUID,
        person_id: UUID,
        payload: PersonVerificationCreate,
    ) -> PersonView:
        """Register habilitation without changing the person's master record."""

        require_pilot_role(self.context.actor, PilotRole.AUDITOR, PilotRole.RESPONSABLE_HYS)
        await self._get_active_worksite(worksite_id)
        assignment = await self.session.scalar(
            select(PersonAssignment).where(
                PersonAssignment.organization_id == PILOT_ORGANIZATION_ID,
                PersonAssignment.worksite_id == worksite_id,
                PersonAssignment.person_id == person_id,
            )
        )
        person = await self._get_person_for_worksite(worksite_id, person_id)
        if assignment is None or person is None:
            raise _not_found()
        function_assignment = await self._require_current_function(
            worksite_id, {"AUDITOR", "RESPONSABLE_HYS_PROYECTO"}
        )
        verification = PersonVerification(
            organization_id=PILOT_ORGANIZATION_ID,
            worksite_id=worksite_id,
            person_id=person_id,
            status=payload.status.value,
            function_label=payload.function_label,
            verified_by_actor_id=self.context.actor.id,
            observation=payload.observation,
        )
        self.session.add(verification)
        await self._flush_or_conflict(
            "person_verification_conflict", "No se pudo registrar la habilitación."
        )
        await self.session.refresh(verification)
        # Keep the function assignment in the audit trail while returning the
        # same person representation used by the worksite detail.
        del function_assignment
        return self._person_view(person, assignment, verification)

    async def create_unregistered_person_finding(
        self,
        audit_id: UUID,
        payload: UnregisteredPersonFindingCreate,
    ) -> FindingView:
        """Create a finding directly; never create a silent personnel record."""

        audit = await self._get_audit(audit_id)
        if audit.status != "EN_CURSO":
            raise _conflict(
                "audit_not_in_progress",
                "Sólo se puede registrar una persona no registrada durante una auditoría en curso.",
            )
        await self._require_current_function(audit.worksite_id, {"AUDITOR"})
        severity = await self._get_severity(payload.severity_code)
        if payload.affected_contractor_id is not None:
            await self._get_worksite_contractor_assignment(
                audit.worksite_id, payload.affected_contractor_id
            )
        (
            responsible_contractor_id,
            responsible_person_id,
        ) = await self._validate_finding_responsibility(
            audit.worksite_id,
            affected_contractor_id=payload.affected_contractor_id,
            responsible_contractor_id=payload.responsible_contractor_id,
            responsible_person_id=payload.responsible_person_id,
        )
        finding = Finding(
            organization_id=PILOT_ORGANIZATION_ID,
            worksite_id=audit.worksite_id,
            audit_id=audit.id,
            title="Persona no registrada en obra",
            description=payload.description,
            status="ABIERTO",
            severity_catalog_version_id=severity.id,
            severity_code=severity.code,
            severity_label=severity.label,
            due_at=_utc_now() + timedelta(days=severity.default_due_days),
            created_by_actor_id=self.context.actor.id,
            affected_contractor_id=payload.affected_contractor_id,
            responsible_contractor_id=responsible_contractor_id,
            responsible_person_id=responsible_person_id,
        )
        self.session.add(finding)
        await self.session.flush()
        self.session.add(
            FindingEvent(
                organization_id=PILOT_ORGANIZATION_ID,
                finding_id=finding.id,
                event_type="UNREGISTERED_PERSON_FOUND",
                from_status=None,
                to_status="ABIERTO",
                actor_id=self.context.actor.id,
                detail="Hallazgo creado sin incorporar una ficha de personal.",
            )
        )
        await self._flush_or_conflict(
            "unregistered_person_finding_conflict", "No se pudo registrar el hallazgo."
        )
        return await self._finding_view(finding)

    async def create_document(
        self,
        worksite_id: UUID,
        payload: DocumentCreate,
    ) -> DocumentView:
        self._require_resource_write()
        worksite = await self._get_active_worksite(worksite_id)
        subject_name = await self._validate_document_subject(worksite, payload)
        subject_contractor_id = await self._document_subject_contractor_id(
            worksite_id, payload.subject_kind, payload.subject_id
        )
        await self._authorize_worksite_write_scope(
            worksite_id,
            contractor_ids={subject_contractor_id} if subject_contractor_id else set(),
            require_contractor_target=subject_contractor_id is not None,
        )
        document = Document(
            organization_id=PILOT_ORGANIZATION_ID,
            title=payload.title,
            document_type=payload.document_type,
            review_status="PENDIENTE",
            valid_from=payload.valid_from,
            expires_on=payload.expires_on,
            notes=payload.notes,
            uploaded_by_actor_id=self.context.actor.id,
            uploaded_at=_utc_now(),
        )
        self.session.add(document)
        await self.session.flush()
        document_version = DocumentVersion(
            organization_id=PILOT_ORGANIZATION_ID,
            document_id=document.id,
            version_number=1,
            title=payload.title,
            document_type=payload.document_type,
            review_status="PENDIENTE",
            valid_from=payload.valid_from,
            expires_on=payload.expires_on,
            notes=payload.notes,
            actor_id=self.context.actor.id,
        )
        self.session.add(document_version)
        association = self._build_document_association(
            document.id,
            worksite_id,
            payload.subject_kind,
            payload.subject_id,
        )
        self.session.add(association)
        await self._flush_or_conflict(
            "document_subject_conflict",
            "El documento debe quedar asociado exactamente a un sujeto visible.",
        )
        await self.session.refresh(document)
        await self.session.refresh(document_version)
        return self._document_view(
            document,
            subject_kind=payload.subject_kind,
            subject_id=payload.subject_id,
            subject_name=subject_name,
            versions=[self._document_version_view(document_version)],
        )

    async def review_document(
        self,
        worksite_id: UUID,
        document_id: UUID,
        payload: DocumentReviewCreate,
    ) -> DocumentView:
        """Record a review separately from document loading and versioning."""

        require_pilot_role(self.context.actor, PilotRole.AUDITOR, PilotRole.RESPONSABLE_HYS)
        await self._get_active_worksite(worksite_id)
        document = await self.session.scalar(
            select(Document)
            .where(Document.organization_id == PILOT_ORGANIZATION_ID, Document.id == document_id)
            .with_for_update()
        )
        if document is None:
            raise _not_found()
        subject = await self._document_subject_for_worksite(worksite_id, document.id)
        if subject is None:
            raise _not_found()
        assignment = await self._require_current_function(worksite_id, _DOCUMENT_REVIEW_FUNCTIONS)
        subject_contractor_id = await self._subject_contractor_id(
            worksite_id, subject[0], subject[1]
        )
        await self._authorize_worksite_write_scope(
            worksite_id,
            contractor_ids={subject_contractor_id} if subject_contractor_id else set(),
            require_contractor_target=subject_contractor_id is not None,
        )
        if document.uploaded_by_actor_id == self.context.actor.id:
            raise _conflict(
                "document_reviewer_must_be_independent",
                "La persona que cargó el documento no puede revisarlo.",
            )
        document.review_status = payload.result
        review = DocumentReview(
            organization_id=PILOT_ORGANIZATION_ID,
            document_id=document.id,
            reviewer_actor_id=self.context.actor.id,
            reviewer_function=assignment.function_code,
            result=payload.result,
            foundation=payload.foundation,
        )
        self.session.add(review)
        await self._flush_or_conflict(
            "document_review_conflict", "No se pudo registrar la revisión documental."
        )
        await self.session.refresh(document)
        await self.session.refresh(review)
        versions = (await self._document_versions_for_documents({document.id})).get(document.id, [])
        reviews = (await self._document_reviews_for_documents({document.id})).get(document.id, [])
        return self._document_view(
            document,
            subject_kind=subject[0],
            subject_id=subject[1],
            subject_name=subject[2],
            versions=versions,
            reviews=reviews,
        )

    async def create_document_version(
        self,
        worksite_id: UUID,
        document_id: UUID,
        payload: DocumentVersionCreate,
    ) -> DocumentView:
        """Append a metadata version and move the document projection atomically."""

        self._require_resource_write()
        worksite = await self._get_active_worksite(worksite_id)
        document = await self.session.scalar(
            select(Document)
            .where(
                Document.organization_id == PILOT_ORGANIZATION_ID,
                Document.id == document_id,
            )
            .with_for_update()
        )
        if document is None:
            raise _not_found()

        subject = await self._document_subject_for_worksite(worksite.id, document.id)
        if subject is None:
            raise _not_found()
        subject_contractor_id = await self._subject_contractor_id(
            worksite.id, subject[0], subject[1]
        )
        await self._authorize_worksite_write_scope(
            worksite.id,
            contractor_ids={subject_contractor_id} if subject_contractor_id else set(),
            require_contractor_target=subject_contractor_id is not None,
        )

        next_version = document.version + 1
        document.title = payload.title
        document.document_type = payload.document_type
        document.review_status = "PENDIENTE"
        document.valid_from = payload.valid_from
        document.expires_on = payload.expires_on
        document.notes = payload.notes
        document.version = next_version
        document_version = DocumentVersion(
            organization_id=PILOT_ORGANIZATION_ID,
            document_id=document.id,
            version_number=next_version,
            title=payload.title,
            document_type=payload.document_type,
            review_status="PENDIENTE",
            valid_from=payload.valid_from,
            expires_on=payload.expires_on,
            notes=payload.notes,
            actor_id=self.context.actor.id,
        )
        self.session.add(document_version)
        await self._flush_or_conflict(
            "document_version_conflict",
            "No se pudo registrar la nueva versión sintética del documento.",
        )
        await self.session.refresh(document)
        await self.session.refresh(document_version)
        versions = (await self._document_versions_for_documents({document.id})).get(document.id, [])
        return self._document_view(
            document,
            subject_kind=subject[0],
            subject_id=subject[1],
            subject_name=subject[2],
            versions=versions,
        )

    async def create_machine(
        self,
        worksite_id: UUID,
        payload: MachineCreate,
    ) -> MachineView:
        self._require_resource_write()
        await self._get_active_worksite(worksite_id)
        started_on = payload.started_on or _today_in_argentina()
        if payload.contractor_id is not None:
            await self._get_contractor_for_worksite(
                worksite_id,
                payload.contractor_id,
                on_date=started_on,
            )
        owner_contractor_id = payload.owner_contractor_id or payload.contractor_id
        if owner_contractor_id is not None:
            await self._get_contractor_for_worksite(
                worksite_id,
                owner_contractor_id,
                on_date=started_on,
            )
        target_contractor_ids = {
            contractor_id
            for contractor_id in (payload.contractor_id, owner_contractor_id)
            if contractor_id is not None
        }
        if payload.operator_person_id is not None:
            operator_assignment = await self._get_person_assignment_for_worksite(
                worksite_id, payload.operator_person_id, on_date=started_on
            )
            if operator_assignment is None:
                raise _not_found()
            if operator_assignment.contractor_id is not None:
                target_contractor_ids.add(operator_assignment.contractor_id)
        await self._authorize_worksite_write_scope(
            worksite_id,
            contractor_ids=target_contractor_ids,
            require_contractor_target=bool(target_contractor_ids),
        )
        machine = Machine(
            organization_id=PILOT_ORGANIZATION_ID,
            internal_code=payload.internal_code,
            description=payload.description,
            status=payload.status.value,
            machine_type=payload.machine_type,
            brand=payload.brand,
            model=payload.model,
            license_plate=payload.license_plate,
            owner_contractor_id=owner_contractor_id,
            operator_person_id=payload.operator_person_id,
        )
        self.session.add(machine)
        await self._flush_or_conflict(
            "duplicate_machine_code",
            "Ya existe una maquinaria sintética con ese código interno.",
        )
        assignment = MachineWorksiteAssignment(
            organization_id=PILOT_ORGANIZATION_ID,
            worksite_id=worksite_id,
            contractor_id=payload.contractor_id,
            machine_id=machine.id,
            started_on=started_on,
            ended_on=payload.ended_on,
        )
        self.session.add(assignment)
        await self._flush_or_conflict(
            "machine_assignment_conflict",
            "No se pudo asignar la maquinaria sintética.",
        )
        await self.session.refresh(machine)
        await self.session.refresh(assignment)
        return self._machine_view(machine, assignment, None)

    async def create_machine_inspection(
        self,
        worksite_id: UUID,
        machine_id: UUID,
        payload: MachineInspectionCreate,
    ) -> MachineView:
        """Append an inspection and update the machine projection atomically."""

        self._require_resource_write()
        await self._get_active_worksite(worksite_id, for_update=True)
        machine = await self.session.scalar(
            select(Machine)
            .join(
                MachineWorksiteAssignment,
                and_(
                    MachineWorksiteAssignment.organization_id == Machine.organization_id,
                    MachineWorksiteAssignment.machine_id == Machine.id,
                ),
            )
            .where(
                Machine.organization_id == PILOT_ORGANIZATION_ID,
                Machine.id == machine_id,
                Machine.deleted_at.is_(None),
                MachineWorksiteAssignment.worksite_id == worksite_id,
            )
            .with_for_update()
        )
        if machine is None:
            raise _not_found()

        assignment = await self.session.scalar(
            select(MachineWorksiteAssignment)
            .where(
                MachineWorksiteAssignment.organization_id == PILOT_ORGANIZATION_ID,
                MachineWorksiteAssignment.machine_id == machine.id,
                MachineWorksiteAssignment.worksite_id == worksite_id,
            )
            .order_by(
                MachineWorksiteAssignment.started_on,
                MachineWorksiteAssignment.created_at,
                MachineWorksiteAssignment.id,
            )
            .limit(1)
        )
        if assignment is None:
            raise _not_found()
        await self._authorize_worksite_write_scope(
            worksite_id,
            contractor_ids={assignment.contractor_id} if assignment.contractor_id else set(),
            require_contractor_target=assignment.contractor_id is not None,
        )

        machine.status = payload.resulting_status.value
        machine.version += 1
        inspection = MachineInspection(
            organization_id=PILOT_ORGANIZATION_ID,
            machine_id=machine.id,
            worksite_id=worksite_id,
            resulting_status=payload.resulting_status.value,
            reason=payload.reason,
            checklist={key: value.value for key, value in payload.checklist.items()},
            evidence_note=payload.evidence_note,
            inspector_function=self._actor_function_label(),
            actor_id=self.context.actor.id,
        )
        self.session.add(inspection)
        await self._flush_or_conflict(
            "machine_inspection_conflict",
            "No se pudo registrar la inspección de la maquinaria.",
        )
        await self.session.refresh(machine)
        await self.session.refresh(inspection)
        inspections = await self._machine_inspections_for_worksite({machine.id}, worksite_id)
        return self._machine_view(
            machine,
            assignment,
            inspection,
            inspections=inspections.get(machine.id, []),
        )

    async def record_machine_inspection(
        self,
        worksite_id: UUID,
        machine_id: UUID,
        payload: MachineInspectionCreate,
    ) -> MachineView:
        """Compatibility name for the machine inspection use case."""

        return await self.create_machine_inspection(worksite_id, machine_id, payload)

    async def validate_machine_inspection(
        self,
        worksite_id: UUID,
        machine_id: UUID,
        inspection_id: UUID,
        payload: MachineInspectionValidationCreate,
    ) -> MachineView:
        require_pilot_role(self.context.actor, PilotRole.AUDITOR, PilotRole.RESPONSABLE_HYS)
        await self._get_active_worksite(worksite_id)
        await self._require_current_function(worksite_id, {"AUDITOR", "RESPONSABLE_HYS_PROYECTO"})
        inspection = await self.session.scalar(
            select(MachineInspection).where(
                MachineInspection.organization_id == PILOT_ORGANIZATION_ID,
                MachineInspection.id == inspection_id,
                MachineInspection.machine_id == machine_id,
                MachineInspection.worksite_id == worksite_id,
            )
        )
        machine = await self.session.scalar(
            select(Machine)
            .join(
                MachineWorksiteAssignment,
                and_(
                    MachineWorksiteAssignment.organization_id == Machine.organization_id,
                    MachineWorksiteAssignment.machine_id == Machine.id,
                    MachineWorksiteAssignment.worksite_id == worksite_id,
                ),
            )
            .where(Machine.organization_id == PILOT_ORGANIZATION_ID, Machine.id == machine_id)
        )
        if inspection is None or machine is None:
            raise _not_found()
        if inspection.actor_id == self.context.actor.id:
            raise _conflict(
                "segregation_of_duties",
                "La persona que realizó la inspección no puede validarla.",
            )
        validation = MachineInspectionValidation(
            organization_id=PILOT_ORGANIZATION_ID,
            inspection_id=inspection.id,
            validated_by_actor_id=self.context.actor.id,
            validator_function=self._actor_function_label(),
            notes=payload.notes,
        )
        self.session.add(validation)
        await self._flush_or_conflict(
            "machine_inspection_validation_conflict", "No se pudo validar la inspección."
        )
        await self.session.refresh(validation)
        assignment = await self.session.scalar(
            select(MachineWorksiteAssignment)
            .where(
                MachineWorksiteAssignment.organization_id == PILOT_ORGANIZATION_ID,
                MachineWorksiteAssignment.worksite_id == worksite_id,
                MachineWorksiteAssignment.machine_id == machine_id,
            )
            .limit(1)
        )
        if assignment is None:
            raise _not_found()
        return self._machine_view(machine, assignment, inspection)

    async def start_audit(
        self,
        worksite_id: UUID,
        payload: AuditStartCreate | None = None,
    ) -> AuditView:
        await self._get_active_worksite(worksite_id)
        auditor_assignment = await self._resolve_auditor_assignment(worksite_id, payload)
        professional_person_id = await self.session.scalar(
            select(WorksiteFunctionalAssignment.person_id)
            .where(
                WorksiteFunctionalAssignment.organization_id == PILOT_ORGANIZATION_ID,
                WorksiteFunctionalAssignment.worksite_id == worksite_id,
                WorksiteFunctionalAssignment.function_code == "RESPONSABLE_HYS_PROYECTO",
                WorksiteFunctionalAssignment.person_id.is_not(None),
                WorksiteFunctionalAssignment.valid_from <= _today_in_argentina(),
                or_(
                    WorksiteFunctionalAssignment.valid_to.is_(None),
                    WorksiteFunctionalAssignment.valid_to > _today_in_argentina(),
                ),
            )
            .order_by(WorksiteFunctionalAssignment.valid_from, WorksiteFunctionalAssignment.id)
            .limit(1)
        )
        catalog = await self.session.scalar(
            select(ControlCatalogVersion)
            .where(
                ControlCatalogVersion.organization_id == PILOT_ORGANIZATION_ID,
                ControlCatalogVersion.code.like("SYN-%"),
                ControlCatalogVersion.published_at.is_not(None),
            )
            .order_by(
                ControlCatalogVersion.published_at.desc(),
                ControlCatalogVersion.version_number.desc(),
                ControlCatalogVersion.code,
                ControlCatalogVersion.id,
            )
            .limit(1)
        )
        if catalog is None:
            raise _conflict(
                "pilot_catalog_unavailable",
                "No hay un catálogo sintético publicado para iniciar la auditoría.",
            )
        audit = Audit(
            organization_id=PILOT_ORGANIZATION_ID,
            worksite_id=worksite_id,
            status="EN_CURSO",
            author_actor_id=auditor_assignment.actor_id,
            editor_actor_id=auditor_assignment.actor_id,
            control_catalog_version_id=catalog.id,
            auditor_actor_id=auditor_assignment.actor_id,
            auditor_assignment_id=auditor_assignment.id,
            associated_professional_person_id=professional_person_id,
            audit_date=_today_in_argentina(),
        )
        self.session.add(audit)
        await self._flush_or_conflict(
            "audit_start_conflict",
            "No se pudo iniciar la auditoría sintética.",
        )
        await self.session.refresh(audit)
        return await self._audit_view(audit)

    async def create_audit_control(
        self,
        audit_id: UUID,
        payload: AuditControlCreate,
    ) -> AuditControlMutationResponse:
        audit = await self._get_audit(audit_id, for_update=True)
        await self._require_audit_editor(audit)
        if audit.status != "EN_CURSO":
            raise _conflict(
                "audit_already_finalized",
                "Una auditoría finalizada no admite nuevos controles.",
            )
        catalog_controls = await self._catalog_controls_for_audit(audit)
        catalog_by_code = {catalog.code: catalog for catalog in catalog_controls}
        catalog = catalog_by_code.get(payload.catalog_code)
        if catalog is None:
            raise _unprocessable(
                "invalid_catalog_control",
                "El código de control no pertenece al catálogo sintético de la auditoría.",
            )
        duplicate_id = await self.session.scalar(
            select(AuditControl.id).where(
                AuditControl.organization_id == PILOT_ORGANIZATION_ID,
                AuditControl.audit_id == audit.id,
                AuditControl.catalog_code == payload.catalog_code,
            )
        )
        if duplicate_id is not None:
            raise _conflict(
                "duplicate_audit_control",
                "Ese control ya fue registrado en la auditoría.",
            )
        control = AuditControl(
            organization_id=PILOT_ORGANIZATION_ID,
            audit_id=audit.id,
            catalog_code=catalog.code,
            catalog_title=catalog.title,
            result=payload.result.value,
            reason=payload.reason,
            recorded_by_actor_id=self.context.actor.id,
        )
        self.session.add(control)
        await self.session.flush()

        finding: Finding | None = None
        if payload.result.value == "NO_CUMPLE":
            severity = await self._get_severity(payload.severity_code)
            if payload.affected_contractor_id is not None:
                await self._get_worksite_contractor_assignment(
                    audit.worksite_id, payload.affected_contractor_id
                )
            (
                responsible_contractor_id,
                responsible_person_id,
            ) = await self._validate_finding_responsibility(
                audit.worksite_id,
                affected_contractor_id=payload.affected_contractor_id,
                responsible_contractor_id=payload.responsible_contractor_id,
                responsible_person_id=payload.responsible_person_id,
            )
            finding = Finding(
                organization_id=PILOT_ORGANIZATION_ID,
                worksite_id=audit.worksite_id,
                audit_id=audit.id,
                title=catalog.title,
                description=cast(str, payload.finding_description),
                status="ABIERTO",
                severity_catalog_version_id=severity.id,
                severity_code=severity.code,
                severity_label=severity.label,
                due_at=_utc_now() + timedelta(days=severity.default_due_days),
                created_by_actor_id=self.context.actor.id,
                affected_contractor_id=payload.affected_contractor_id,
                responsible_contractor_id=responsible_contractor_id,
                responsible_person_id=responsible_person_id,
            )
            self.session.add(finding)
            await self.session.flush()
            self.session.add_all(
                [
                    FindingControl(
                        organization_id=PILOT_ORGANIZATION_ID,
                        finding_id=finding.id,
                        audit_control_id=control.id,
                    ),
                    FindingEvent(
                        organization_id=PILOT_ORGANIZATION_ID,
                        finding_id=finding.id,
                        event_type="CREATED_FROM_CONTROL",
                        from_status=None,
                        to_status="ABIERTO",
                        actor_id=self.context.actor.id,
                        detail="Desvío creado desde un control NO_CUMPLE.",
                    ),
                ]
            )
        await self._flush_or_conflict(
            "audit_control_conflict",
            "No se pudo registrar el control y su desvío de forma atómica.",
        )
        await self.session.refresh(control)
        control_view = self._audit_control_view(control, finding.id if finding else None)
        finding_view = await self._finding_view(finding) if finding is not None else None
        return AuditControlMutationResponse(control=control_view, finding=finding_view)

    async def finalize_audit(self, audit_id: UUID) -> AuditView:
        audit = await self._get_audit(audit_id, for_update=True)
        await self._require_audit_editor(audit)
        if audit.status != "EN_CURSO":
            raise _conflict("audit_already_finalized", "La auditoría ya está finalizada.")
        catalog_controls = await self._catalog_controls_for_audit(audit)
        answered_codes = set(
            await self.session.scalars(
                select(AuditControl.catalog_code).where(
                    AuditControl.organization_id == PILOT_ORGANIZATION_ID,
                    AuditControl.audit_id == audit.id,
                )
            )
        )
        missing_codes = sorted({catalog.code for catalog in catalog_controls} - answered_codes)
        if missing_codes:
            missing = ", ".join(missing_codes)
            raise _conflict(
                "audit_controls_incomplete",
                f"Respondé todos los controles antes de finalizar la auditoría. Faltan: {missing}.",
            )
        audit.status = "FINALIZADA"
        audit.finalized_at = _utc_now()
        audit.version += 1
        await self.session.flush()
        await self.session.refresh(audit)
        return await self._audit_view(audit)

    async def create_correction(
        self,
        finding_id: UUID,
        payload: CorrectionCreate,
    ) -> FindingView:
        self._require_correction_write()
        finding = await self._get_finding(finding_id, for_update=True)
        await self._require_current_function(finding.worksite_id, _ALL_FUNCTIONS)
        await self._authorize_finding_scope(finding)
        if finding.status not in {"ABIERTO", "EN_CORRECCION"}:
            raise _conflict(
                "finding_not_correctable",
                "El desvío no admite correcciones en su estado actual.",
            )
        previous_status = finding.status
        correction = Correction(
            organization_id=PILOT_ORGANIZATION_ID,
            finding_id=finding.id,
            description=payload.description,
            evidence_note=payload.evidence_note,
            authored_by_actor_id=self.context.actor.id,
        )
        finding.status = "EN_CORRECCION"
        finding.version += 1
        event = FindingEvent(
            organization_id=PILOT_ORGANIZATION_ID,
            finding_id=finding.id,
            event_type="CORRECTION_ADDED",
            from_status=previous_status,
            to_status="EN_CORRECCION",
            actor_id=self.context.actor.id,
            detail="Se agregó una corrección con evidencia sintética.",
        )
        self.session.add_all([correction, event])
        await self.session.flush()
        return await self._finding_view(finding)

    async def submit_verification(self, finding_id: UUID) -> FindingView:
        self._require_correction_write()
        finding = await self._get_finding(finding_id, for_update=True)
        await self._require_current_function(finding.worksite_id, _ALL_FUNCTIONS)
        await self._authorize_finding_scope(finding)
        if finding.status != "EN_CORRECCION":
            raise _conflict(
                "finding_not_ready_for_verification",
                "El desvío debe estar en corrección antes de enviarse a verificación.",
            )
        correction = await self._latest_correction(finding.id)
        if correction is None:
            raise _conflict(
                "finding_has_no_correction",
                "El desvío necesita una corrección antes de enviarse a verificación.",
            )
        if correction.authored_by_actor_id != self.context.actor.id:
            raise ProblemException(
                status=403,
                code="correction_author_required",
                title="Acceso denegado",
                detail="Sólo el autor de la última corrección puede enviarla a verificación.",
            )
        finding.status = "PENDIENTE_VERIFICACION"
        finding.version += 1
        self.session.add(
            FindingEvent(
                organization_id=PILOT_ORGANIZATION_ID,
                finding_id=finding.id,
                event_type="SUBMITTED_FOR_VERIFICATION",
                from_status="EN_CORRECCION",
                to_status="PENDIENTE_VERIFICACION",
                actor_id=self.context.actor.id,
                detail="La última corrección fue enviada a verificación.",
            )
        )
        await self.session.flush()
        return await self._finding_view(finding)

    async def verify_finding(
        self,
        finding_id: UUID,
        payload: VerificationCreate,
    ) -> FindingView:
        require_pilot_role(self.context.actor, PilotRole.AUDITOR, PilotRole.RESPONSABLE_HYS)
        finding = await self._get_finding(finding_id, for_update=True)
        if finding.status != "PENDIENTE_VERIFICACION":
            raise _conflict(
                "finding_not_pending_verification",
                "El desvío no está pendiente de verificación.",
            )
        correction = await self._latest_correction(finding.id)
        if correction is None:
            raise _conflict(
                "finding_has_no_correction",
                "El desvío no tiene una corrección verificable.",
            )
        if self.context.actor.id == correction.authored_by_actor_id:
            raise _conflict(
                "segregation_of_duties",
                "El autor de la corrección no puede verificarla.",
            )
        await self._require_current_function(
            finding.worksite_id,
            {
                "AUDITOR",
                "RESPONSABLE_HYS_PROYECTO",
                "RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL",
            },
        )
        await self._authorize_finding_scope(finding)
        previous_status = finding.status
        if payload.decision is VerificationDecision.ACEPTADA:
            target_status = "CERRADO"
            finding.closed_at = _utc_now()
        else:
            target_status = "EN_CORRECCION"
            finding.closed_at = None
        finding.status = target_status
        finding.version += 1
        verification = Verification(
            organization_id=PILOT_ORGANIZATION_ID,
            finding_id=finding.id,
            decision=payload.decision.value,
            notes=payload.notes,
            verified_by_actor_id=self.context.actor.id,
        )
        event = FindingEvent(
            organization_id=PILOT_ORGANIZATION_ID,
            finding_id=finding.id,
            event_type=f"VERIFICATION_{payload.decision.value}",
            from_status=previous_status,
            to_status=target_status,
            actor_id=self.context.actor.id,
            detail=payload.notes,
        )
        self.session.add_all([verification, event])
        await self.session.flush()
        return await self._finding_view(finding)

    async def get_finding_timeline(self, finding_id: UUID) -> FindingTimeline:
        finding = await self._get_finding(finding_id)
        events = await self._events_for_finding(finding.id)
        return FindingTimeline(finding_id=finding.id, events=events)

    def _require_resource_write(self) -> None:
        require_pilot_role(
            self.context.actor,
            PilotRole.TECNICO,
            PilotRole.RESPONSABLE_HYS,
        )

    def _require_correction_write(self) -> None:
        require_pilot_role(
            self.context.actor,
            PilotRole.TECNICO,
            PilotRole.RESPONSABLE_HYS,
        )

    def _actor_function_label(self) -> str:
        labels = {
            "auditor": "Auditor",
            "tecnico": "Técnico H&S de contratista principal",
            "responsable": "Licenciado H&S del proyecto",
            "responsable-suplente": "Licenciado H&S de contratista principal",
            "licenciado-contratista-principal": "Licenciado H&S de contratista principal",
            "contratista-principal": "Cuenta organizacional de contratista principal",
        }
        return labels.get(self.context.actor.key, "Función H&S del piloto")

    async def _active_functional_assignments(
        self, worksite_id: UUID, function_codes: Collection[str] = _ALL_FUNCTIONS
    ) -> list[WorksiteFunctionalAssignment]:
        today = _today_in_argentina()
        assignments = await self.session.scalars(
            select(WorksiteFunctionalAssignment)
            .where(
                WorksiteFunctionalAssignment.organization_id == PILOT_ORGANIZATION_ID,
                WorksiteFunctionalAssignment.worksite_id == worksite_id,
                WorksiteFunctionalAssignment.actor_id == self.context.actor.id,
                WorksiteFunctionalAssignment.function_code.in_(function_codes),
                WorksiteFunctionalAssignment.valid_from <= today,
                or_(
                    WorksiteFunctionalAssignment.valid_to.is_(None),
                    WorksiteFunctionalAssignment.valid_to > today,
                ),
            )
            .order_by(WorksiteFunctionalAssignment.valid_from, WorksiteFunctionalAssignment.id)
        )
        return list(assignments)

    async def _contractor_scope_ids(self, worksite_id: UUID) -> set[UUID]:
        if self.context.actor.key not in _CONTRACTOR_ACTOR_KEYS:
            return set()
        assignments = await self._active_functional_assignments(worksite_id, _CONTRACTOR_FUNCTIONS)
        return {
            assignment.represented_contractor_id
            for assignment in assignments
            if assignment.represented_contractor_id is not None
        }

    async def _authorize_worksite_write_scope(
        self,
        worksite_id: UUID,
        *,
        contractor_ids: set[UUID] | None = None,
        require_contractor_target: bool = False,
    ) -> None:
        """Enforce the company represented by contractor professionals."""

        if self.context.actor.key not in _CONTRACTOR_ACTOR_KEYS:
            return
        if not require_contractor_target and not contractor_ids:
            return
        scope_ids = await self._contractor_scope_ids(worksite_id)
        if not scope_ids:
            worksite = await self._get_worksite(worksite_id)
            if worksite.created_by_actor_id == self.context.actor.id:
                return
            raise ProblemException(
                status=403,
                code="pilot_assignment_required",
                title="Asignación funcional requerida",
                detail="El profesional no tiene una representación vigente para esta obra.",
            )
        targets = contractor_ids or set()
        if require_contractor_target and not targets:
            raise ProblemException(
                status=403,
                code="pilot_contractor_scope_denied",
                title="Alcance de contratista insuficiente",
                detail=(
                    "La operación debe indicar una empresa representada dentro del alcance vigente."
                ),
            )
        if not targets.issubset(scope_ids):
            raise ProblemException(
                status=403,
                code="pilot_contractor_scope_denied",
                title="Alcance de contratista insuficiente",
                detail="La operación excede la empresa representada por el profesional.",
            )

    async def _authorize_finding_scope(self, finding: Finding) -> None:
        if self.context.actor.key not in _CONTRACTOR_ACTOR_KEYS:
            return
        contractor_id = finding.responsible_contractor_id or finding.affected_contractor_id
        if contractor_id is None:
            raise ProblemException(
                status=403,
                code="pilot_contractor_scope_denied",
                title="Alcance de contratista insuficiente",
                detail="El desvío no tiene una empresa responsable asignada para este alcance.",
            )
        await self._authorize_worksite_write_scope(
            finding.worksite_id,
            contractor_ids={contractor_id},
            require_contractor_target=True,
        )

    async def _require_audit_editor(self, audit: Audit) -> None:
        if audit.editor_actor_id != self.context.actor.id or (
            audit.auditor_actor_id is not None and audit.auditor_actor_id != self.context.actor.id
        ):
            raise ProblemException(
                status=403,
                code="audit_editor_required",
                title="Acceso denegado",
                detail="Sólo el editor de la auditoría puede modificarla o finalizarla.",
            )
        if audit.auditor_assignment_id is None:
            raise ProblemException(
                status=403,
                code="audit_assignment_required",
                title="Acceso denegado",
                detail="La auditoría no tiene una asignación AUDITOR vigente asociada.",
            )
        await self._require_current_function(
            audit.worksite_id,
            {"AUDITOR"},
            assignment_id=audit.auditor_assignment_id,
        )

    def _add_compatibility_assignments(self, worksite_id: UUID) -> None:
        """Keep legacy selectors usable for an otherwise empty worksite only."""

        assignments = (
            ("auditor", "AUDITOR"),
            ("tecnico", "TECNICO_HYS_CONTRATISTA_PRINCIPAL"),
            ("responsable", "RESPONSABLE_HYS_PROYECTO"),
            ("responsable-suplente", "RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL"),
        )
        for actor_key, function_code in assignments:
            actor = PILOT_ACTORS[actor_key]
            self.session.add(
                WorksiteFunctionalAssignment(
                    organization_id=PILOT_ORGANIZATION_ID,
                    worksite_id=worksite_id,
                    actor_id=actor.id,
                    function_code=function_code,
                    valid_from=_today_in_argentina(),
                )
            )

    async def _resolve_auditor_assignment(
        self,
        worksite_id: UUID,
        payload: AuditStartCreate | None,
    ) -> WorksiteFunctionalAssignment:
        today = _today_in_argentina()
        statement = select(WorksiteFunctionalAssignment).where(
            WorksiteFunctionalAssignment.organization_id == PILOT_ORGANIZATION_ID,
            WorksiteFunctionalAssignment.worksite_id == worksite_id,
            WorksiteFunctionalAssignment.actor_id == self.context.actor.id,
            WorksiteFunctionalAssignment.function_code == "AUDITOR",
            WorksiteFunctionalAssignment.valid_from <= today,
            or_(
                WorksiteFunctionalAssignment.valid_to.is_(None),
                WorksiteFunctionalAssignment.valid_to > today,
            ),
        )
        if payload is not None and payload.auditor_assignment_id is not None:
            statement = statement.where(
                WorksiteFunctionalAssignment.id == payload.auditor_assignment_id
            )
        assignment = await self.session.scalar(
            statement.order_by(WorksiteFunctionalAssignment.id).limit(1)
        )
        if assignment is None:
            raise ProblemException(
                status=403,
                code="pilot_assignment_required",
                title="Asignación funcional requerida",
                detail="El actor no tiene una asignación de auditoría vigente para esta obra.",
            )
        self._check_assignment_scope(assignment)
        return assignment

    async def _require_current_function(
        self,
        worksite_id: UUID,
        function_codes: Collection[str],
        *,
        assignment_id: UUID | None = None,
    ) -> WorksiteFunctionalAssignment:
        today = _today_in_argentina()
        statement = select(WorksiteFunctionalAssignment).where(
            WorksiteFunctionalAssignment.organization_id == PILOT_ORGANIZATION_ID,
            WorksiteFunctionalAssignment.worksite_id == worksite_id,
            WorksiteFunctionalAssignment.actor_id == self.context.actor.id,
            WorksiteFunctionalAssignment.function_code.in_(function_codes),
            WorksiteFunctionalAssignment.valid_from <= today,
            or_(
                WorksiteFunctionalAssignment.valid_to.is_(None),
                WorksiteFunctionalAssignment.valid_to > today,
            ),
        )
        if assignment_id is not None:
            statement = statement.where(WorksiteFunctionalAssignment.id == assignment_id)
        assignment = await self.session.scalar(
            statement.order_by(
                WorksiteFunctionalAssignment.valid_from, WorksiteFunctionalAssignment.id
            ).limit(1)
        )
        if assignment is None:
            raise ProblemException(
                status=403,
                code="pilot_assignment_required",
                title="Asignación funcional requerida",
                detail="El actor no tiene la función vigente para esta obra.",
            )
        self._check_assignment_scope(assignment)
        return assignment

    def _check_assignment_scope(self, assignment: WorksiteFunctionalAssignment) -> None:
        if (
            assignment.permission_scope == "ORGANIZATION"
            and self.context.actor.permission_scope != "ORGANIZATION"
        ):
            raise ProblemException(
                status=403,
                code="pilot_scope_denied",
                title="Acceso denegado",
                detail="El alcance de la asignación excede el alcance del actor.",
            )

    async def create_functional_assignment(
        self,
        worksite_id: UUID,
        payload: WorksiteFunctionalAssignmentCreate,
    ) -> WorksiteFunctionalAssignmentView:
        self._require_resource_write()
        await self._require_worksite_setup_access(worksite_id)
        if payload.actor_id not in {actor.id for actor in PILOT_ACTORS.values()}:
            raise _unprocessable(
                "invalid_pilot_actor", "El actor debe pertenecer al adaptador sintético."
            )
        valid_from = payload.valid_from or _today_in_argentina()
        if payload.valid_to is not None and payload.valid_to <= valid_from:
            raise _unprocessable(
                "invalid_functional_assignment_interval",
                "valid_to debe ser posterior a valid_from.",
            )
        if payload.permission_scope.value == "ORGANIZATION" and (
            self.context.actor.permission_scope != "ORGANIZATION"
        ):
            raise ProblemException(
                status=403,
                code="pilot_scope_denied",
                title="Acceso denegado",
                detail="El alcance de la asignación excede el alcance del actor.",
            )

        function_code = payload.function_code.value
        if payload.person_id is None:
            raise _unprocessable(
                "functional_assignment_person_required",
                "Una asignación funcional debe identificar a la persona del actor.",
            )
        person = await self._get_person_for_worksite(
            worksite_id,
            payload.person_id,
            on_date=valid_from,
        )
        if person is None:
            raise _not_found()
        if function_code == "AUDITOR":
            expected_professions = {"LICENCIADO_HYS", "TECNICO_HYS"}
        else:
            expected_professions = {
                "LICENCIADO_HYS" if function_code in _RESPONSIBLE_FUNCTIONS else "TECNICO_HYS"
            }
        if person.profession_code not in expected_professions:
            raise _unprocessable(
                "profession_function_mismatch",
                "La profesión de la persona no coincide con la función funcional solicitada.",
            )

        if function_code == "AUDITOR":
            if person.profession_code == "TECNICO_HYS":
                if payload.delegated_by_assignment_id is None:
                    raise _unprocessable(
                        "auditor_delegation_required",
                        "Un técnico auditor debe indicar la asignación "
                        "RESPONSABLE_HYS_PROYECTO que lo delega.",
                    )
                delegating_assignment = await self.session.scalar(
                    select(WorksiteFunctionalAssignment).where(
                        WorksiteFunctionalAssignment.organization_id == PILOT_ORGANIZATION_ID,
                        WorksiteFunctionalAssignment.worksite_id == worksite_id,
                        WorksiteFunctionalAssignment.id == payload.delegated_by_assignment_id,
                        WorksiteFunctionalAssignment.function_code == "RESPONSABLE_HYS_PROYECTO",
                        WorksiteFunctionalAssignment.person_id.is_not(None),
                        WorksiteFunctionalAssignment.represented_contractor_id.is_(None),
                        WorksiteFunctionalAssignment.valid_from <= valid_from,
                        or_(
                            WorksiteFunctionalAssignment.valid_to.is_(None),
                            WorksiteFunctionalAssignment.valid_to > valid_from,
                        ),
                    )
                )
                if delegating_assignment is None:
                    raise _unprocessable(
                        "invalid_auditor_delegation",
                        "La delegación debe apuntar a una asignación "
                        "RESPONSABLE_HYS_PROYECTO vigente de la misma obra.",
                    )
                delegating_person = await self.session.scalar(
                    select(Person).where(
                        Person.organization_id == PILOT_ORGANIZATION_ID,
                        Person.id == delegating_assignment.person_id,
                    )
                )
                if (
                    delegating_person is None
                    or delegating_person.profession_code != "LICENCIADO_HYS"
                ):
                    raise _unprocessable(
                        "invalid_auditor_delegation",
                        "La delegación debe provenir de un Licenciado H&S "
                        "responsable del proyecto.",
                    )
            elif payload.delegated_by_assignment_id is not None:
                raise _unprocessable(
                    "auditor_delegation_not_allowed",
                    "La delegación no corresponde a un Auditor Licenciado H&S.",
                )

        expected_profession = person.profession_code

        actor = next(
            candidate for candidate in PILOT_ACTORS.values() if candidate.id == payload.actor_id
        )
        if actor.profession_code != expected_profession:
            raise _unprocessable(
                "actor_function_mismatch",
                "La profesión del actor sintético no coincide con la función solicitada.",
            )

        if function_code in _PROJECT_FUNCTIONS:
            expected_actor_key = (
                "auditor"
                if function_code == "AUDITOR" and expected_profession == "TECNICO_HYS"
                else "responsable"
            )
            if actor.key != expected_actor_key:
                raise _unprocessable(
                    "project_actor_function_mismatch",
                    "La función de proyecto debe asignarse al actor profesional del proyecto.",
                )
            if payload.represented_contractor_id is not None:
                raise _unprocessable(
                    "project_function_contractor_forbidden",
                    "Una función de proyecto no puede representar a un contratista.",
                )
        elif payload.delegated_by_assignment_id is not None:
            raise _unprocessable(
                "delegation_only_for_auditor",
                "La delegación sólo puede informarse para una función AUDITOR.",
            )
        elif payload.represented_contractor_id is None:
            raise _unprocessable(
                "represented_contractor_required",
                "Una función de contratista debe indicar la empresa representada.",
            )
        else:
            expected_actor_key = {
                "RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL": "responsable-suplente",
                "TECNICO_HYS_CONTRATISTA_PRINCIPAL": "tecnico",
                "RESPONSABLE_HYS_CONTRATISTA": "licenciado-contratista",
                "TECNICO_HYS_CONTRATISTA": "tecnico-contratista",
            }[function_code]
            if actor.key != expected_actor_key:
                raise _unprocessable(
                    "contractor_actor_function_mismatch",
                    "La función de contratista debe asignarse al profesional sintético "
                    "correspondiente.",
                )
            await self._authorize_worksite_write_scope(
                worksite_id,
                contractor_ids={payload.represented_contractor_id},
                require_contractor_target=True,
            )
            participant = await self._get_worksite_contractor_assignment(
                worksite_id,
                payload.represented_contractor_id,
                on_date=valid_from,
            )
            if (
                function_code in _PRINCIPAL_CONTRACTOR_FUNCTIONS
                and participant.participation_type != ContractorParticipationType.PRINCIPAL.value
            ):
                raise _unprocessable(
                    "principal_contractor_required",
                    "La función de contratista principal debe representar al "
                    "contratista principal.",
                )
            expected_participation = (
                ContractorParticipationType.PRINCIPAL.value
                if function_code in _PRINCIPAL_CONTRACTOR_FUNCTIONS
                else ContractorParticipationType.CONTRACTOR.value
            )
            if participant.participation_type != expected_participation:
                raise _unprocessable(
                    "contractor_participation_mismatch",
                    "La función debe representar una empresa con el tipo de "
                    "participación correspondiente.",
                )
            person_assignment = await self._get_person_assignment_for_worksite(
                worksite_id, payload.person_id, on_date=valid_from
            )
            if (
                person_assignment is None
                or person_assignment.contractor_id != participant.contractor_id
            ):
                raise _unprocessable(
                    "represented_company_mismatch",
                    "La persona asignada debe pertenecer a la empresa que representa.",
                )
        assignment = WorksiteFunctionalAssignment(
            organization_id=PILOT_ORGANIZATION_ID,
            worksite_id=worksite_id,
            actor_id=payload.actor_id,
            person_id=payload.person_id,
            function_code=payload.function_code.value,
            represented_contractor_id=payload.represented_contractor_id,
            delegated_by_assignment_id=payload.delegated_by_assignment_id,
            permission_scope=payload.permission_scope.value,
            valid_from=valid_from,
            valid_to=payload.valid_to,
        )
        self.session.add(assignment)
        await self._flush_or_conflict(
            "functional_assignment_conflict",
            "No se pudo guardar la asignación funcional de la obra.",
        )
        await self.session.refresh(assignment)
        return await self._functional_assignment_view(assignment)

    async def list_functional_assignments(
        self, worksite_id: UUID
    ) -> list[WorksiteFunctionalAssignmentView]:
        await self._require_worksite_setup_access(worksite_id, active=False)
        assignments = await self._functional_assignments_for_worksite(worksite_id)
        scope_ids = await self._contractor_scope_ids(worksite_id)
        if scope_ids:
            assignments = [
                item for item in assignments if item.represented_contractor_id in scope_ids
            ]
        return assignments

    async def _flush_or_conflict(self, code: str, detail: str) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise _conflict(code, detail) from exc

    def _allowed_assignment_scope(self) -> ColumnElement[bool]:
        allowed_scope = WorksiteFunctionalAssignment.permission_scope == "WORKSITE"
        if self.context.actor.permission_scope == "ORGANIZATION":
            return or_(
                allowed_scope,
                WorksiteFunctionalAssignment.permission_scope == "ORGANIZATION",
            )
        return allowed_scope

    async def _require_worksite_setup_access(
        self, worksite_id: UUID, *, active: bool = True
    ) -> Worksite:
        worksite = (
            await self._get_active_worksite(worksite_id)
            if active
            else await self._get_worksite(worksite_id)
        )
        if worksite.created_by_actor_id == self.context.actor.id:
            return worksite
        if self.context.actor.role is PilotRole.CONTRATISTA:
            raise ProblemException(
                status=403,
                code="pilot_read_only_organization_account",
                title="Cuenta organizacional de solo lectura",
                detail=(
                    "La cuenta organizacional puede consultar la obra, pero no configurar actores."
                ),
            )
        await self._require_current_function(worksite_id, _ALL_FUNCTIONS)
        return worksite

    async def _get_worksite(
        self,
        worksite_id: UUID,
        *,
        for_update: bool = False,
        require_scope: bool = False,
    ) -> Worksite:
        statement = select(Worksite).where(
            Worksite.organization_id == PILOT_ORGANIZATION_ID,
            Worksite.id == worksite_id,
            Worksite.deleted_at.is_(None),
        )
        if require_scope:
            today = _today_in_argentina()
            statement = statement.where(
                or_(
                    Worksite.created_by_actor_id == self.context.actor.id,
                    literal(self.context.actor.role is PilotRole.CONTRATISTA),
                    exists(
                        select(WorksiteFunctionalAssignment.id).where(
                            WorksiteFunctionalAssignment.organization_id
                            == Worksite.organization_id,
                            WorksiteFunctionalAssignment.worksite_id == Worksite.id,
                            WorksiteFunctionalAssignment.actor_id == self.context.actor.id,
                            self._allowed_assignment_scope(),
                            WorksiteFunctionalAssignment.valid_from <= today,
                            or_(
                                WorksiteFunctionalAssignment.valid_to.is_(None),
                                WorksiteFunctionalAssignment.valid_to > today,
                            ),
                        )
                    ),
                )
            )
        if for_update:
            statement = statement.with_for_update()
        worksite = await self.session.scalar(statement)
        if worksite is None:
            raise _not_found()
        return worksite

    async def _require_read_access(self, worksite_id: UUID) -> Worksite:
        """Allow explicit assignments, setup ownership, or the org read-only view."""

        worksite = await self._get_worksite(worksite_id, require_scope=True)
        if self.context.actor.role is PilotRole.CONTRATISTA:
            return worksite
        if worksite.created_by_actor_id == self.context.actor.id:
            return worksite
        await self._require_current_function(worksite_id, _ALL_FUNCTIONS)
        return worksite

    async def _get_active_worksite(
        self,
        worksite_id: UUID,
        *,
        for_update: bool = False,
    ) -> Worksite:
        worksite = await self._get_worksite(
            worksite_id,
            for_update=for_update,
            require_scope=True,
        )
        if worksite.status != "ACTIVE":
            raise _conflict(
                "worksite_archived",
                "Una obra archivada no admite nuevas operaciones del piloto.",
            )
        return worksite

    async def _get_audit(self, audit_id: UUID, *, for_update: bool = False) -> Audit:
        statement = select(Audit).where(
            Audit.organization_id == PILOT_ORGANIZATION_ID,
            Audit.id == audit_id,
        )
        if for_update:
            statement = statement.with_for_update()
        audit = await self.session.scalar(statement)
        if audit is None:
            raise _not_found()
        return audit

    async def _get_finding(self, finding_id: UUID, *, for_update: bool = False) -> Finding:
        statement = select(Finding).where(
            Finding.organization_id == PILOT_ORGANIZATION_ID,
            Finding.id == finding_id,
        )
        if for_update:
            statement = statement.with_for_update()
        finding = await self.session.scalar(statement)
        if finding is None:
            raise _not_found()
        return finding

    async def _get_contractor_for_worksite(
        self,
        worksite_id: UUID,
        contractor_id: UUID,
        *,
        on_date: date | None = None,
    ) -> Contractor:
        statement = (
            select(Contractor)
            .join(
                WorksiteContractor,
                and_(
                    WorksiteContractor.organization_id == Contractor.organization_id,
                    WorksiteContractor.contractor_id == Contractor.id,
                ),
            )
            .where(
                Contractor.organization_id == PILOT_ORGANIZATION_ID,
                Contractor.id == contractor_id,
                Contractor.deleted_at.is_(None),
                WorksiteContractor.worksite_id == worksite_id,
            )
        )
        if on_date is not None:
            statement = statement.where(
                WorksiteContractor.started_on <= on_date,
                or_(
                    WorksiteContractor.ended_on.is_(None),
                    WorksiteContractor.ended_on > on_date,
                ),
            )
        contractor = await self.session.scalar(statement.limit(1))
        if contractor is None:
            raise _not_found()
        return contractor

    async def _get_worksite_contractor_assignment(
        self,
        worksite_id: UUID,
        contractor_id: UUID,
        *,
        on_date: date | None = None,
    ) -> WorksiteContractor:
        statement = select(WorksiteContractor).where(
            WorksiteContractor.organization_id == PILOT_ORGANIZATION_ID,
            WorksiteContractor.worksite_id == worksite_id,
            WorksiteContractor.contractor_id == contractor_id,
        )
        if on_date is not None:
            statement = statement.where(
                WorksiteContractor.started_on <= on_date,
                or_(
                    WorksiteContractor.ended_on.is_(None),
                    WorksiteContractor.ended_on > on_date,
                ),
            )
        participant = await self.session.scalar(statement.limit(1))
        if participant is None:
            raise _not_found()
        return participant

    async def _get_person_for_worksite(
        self,
        worksite_id: UUID,
        person_id: UUID,
        *,
        on_date: date | None = None,
    ) -> Person | None:
        statement = (
            select(Person)
            .join(
                PersonAssignment,
                and_(
                    PersonAssignment.organization_id == Person.organization_id,
                    PersonAssignment.person_id == Person.id,
                ),
            )
            .where(
                Person.organization_id == PILOT_ORGANIZATION_ID,
                Person.id == person_id,
                Person.deleted_at.is_(None),
                PersonAssignment.organization_id == PILOT_ORGANIZATION_ID,
                PersonAssignment.worksite_id == worksite_id,
            )
        )
        if on_date is not None:
            statement = statement.where(
                PersonAssignment.started_on <= on_date,
                or_(
                    PersonAssignment.ended_on.is_(None),
                    PersonAssignment.ended_on > on_date,
                ),
            )
        return cast(Person | None, await self.session.scalar(statement.limit(1)))

    async def _get_person_assignment_for_worksite(
        self,
        worksite_id: UUID,
        person_id: UUID,
        *,
        on_date: date | None = None,
    ) -> PersonAssignment | None:
        statement = select(PersonAssignment).where(
            PersonAssignment.organization_id == PILOT_ORGANIZATION_ID,
            PersonAssignment.worksite_id == worksite_id,
            PersonAssignment.person_id == person_id,
        )
        if on_date is not None:
            statement = statement.where(
                PersonAssignment.started_on <= on_date,
                or_(
                    PersonAssignment.ended_on.is_(None),
                    PersonAssignment.ended_on > on_date,
                ),
            )
        return cast(PersonAssignment | None, await self.session.scalar(statement.limit(1)))

    async def _validate_finding_responsibility(
        self,
        worksite_id: UUID,
        *,
        affected_contractor_id: UUID | None,
        responsible_contractor_id: UUID | None,
        responsible_person_id: UUID | None,
    ) -> tuple[UUID | None, UUID | None]:
        contractor_id = responsible_contractor_id or affected_contractor_id
        if contractor_id is not None:
            await self._get_worksite_contractor_assignment(worksite_id, contractor_id)
        if responsible_person_id is None:
            return contractor_id, None
        person_assignment = await self._get_person_assignment_for_worksite(
            worksite_id, responsible_person_id
        )
        if person_assignment is None:
            raise _not_found()
        if (
            person_assignment.contractor_id is not None
            and contractor_id is not None
            and person_assignment.contractor_id != contractor_id
        ):
            raise _unprocessable(
                "responsibility_scope_mismatch",
                "La persona responsable debe pertenecer a la empresa responsable indicada.",
            )
        return contractor_id, responsible_person_id

    async def _document_subject_contractor_id(
        self, worksite_id: UUID, subject_kind: SubjectKind, subject_id: UUID
    ) -> UUID | None:
        if subject_kind is SubjectKind.CONTRACTOR:
            return subject_id
        if subject_kind is SubjectKind.PERSON:
            assignment = await self._get_person_assignment_for_worksite(worksite_id, subject_id)
            return assignment.contractor_id if assignment else None
        if subject_kind is SubjectKind.MACHINE:
            machine = await self.session.scalar(
                select(Machine)
                .join(
                    MachineWorksiteAssignment,
                    and_(
                        MachineWorksiteAssignment.organization_id == Machine.organization_id,
                        MachineWorksiteAssignment.machine_id == Machine.id,
                        MachineWorksiteAssignment.worksite_id == worksite_id,
                    ),
                )
                .where(
                    Machine.organization_id == PILOT_ORGANIZATION_ID,
                    Machine.id == subject_id,
                )
                .limit(1)
            )
            return machine.owner_contractor_id if machine else None
        return None

    async def _subject_contractor_id(
        self, worksite_id: UUID, subject_kind: SubjectKind, subject_id: UUID
    ) -> UUID | None:
        return await self._document_subject_contractor_id(worksite_id, subject_kind, subject_id)

    async def _get_severity(self, severity_code: str | None) -> SeverityCatalogVersion:
        if severity_code is None:
            raise _unprocessable(
                "severity_required",
                "severity_code es obligatorio para un control NO_CUMPLE.",
            )
        severity = await self.session.scalar(
            select(SeverityCatalogVersion)
            .where(
                SeverityCatalogVersion.organization_id == PILOT_ORGANIZATION_ID,
                SeverityCatalogVersion.code == severity_code,
                SeverityCatalogVersion.published_at.is_not(None),
            )
            .order_by(SeverityCatalogVersion.version_number.desc())
            .limit(1)
        )
        if severity is None:
            raise _unprocessable(
                "invalid_severity",
                "La severidad no pertenece al catálogo sintético publicado.",
            )
        return severity

    async def _validate_document_subject(
        self,
        worksite: Worksite,
        payload: DocumentCreate,
    ) -> str:
        if payload.subject_kind is SubjectKind.WORKSITE:
            if payload.subject_id != worksite.id:
                raise _not_found()
            return worksite.name
        if payload.subject_kind is SubjectKind.CONTRACTOR:
            contractor = await self._get_contractor_for_worksite(
                worksite.id,
                payload.subject_id,
            )
            return contractor.legal_name
        if payload.subject_kind is SubjectKind.PERSON:
            person = await self.session.scalar(
                select(Person)
                .join(
                    PersonAssignment,
                    and_(
                        PersonAssignment.organization_id == Person.organization_id,
                        PersonAssignment.person_id == Person.id,
                    ),
                )
                .where(
                    Person.organization_id == PILOT_ORGANIZATION_ID,
                    Person.id == payload.subject_id,
                    Person.deleted_at.is_(None),
                    PersonAssignment.worksite_id == worksite.id,
                )
                .limit(1)
            )
            if person is None:
                raise _not_found()
            return person.display_name
        machine = await self.session.scalar(
            select(Machine)
            .join(
                MachineWorksiteAssignment,
                and_(
                    MachineWorksiteAssignment.organization_id == Machine.organization_id,
                    MachineWorksiteAssignment.machine_id == Machine.id,
                ),
            )
            .where(
                Machine.organization_id == PILOT_ORGANIZATION_ID,
                Machine.id == payload.subject_id,
                Machine.deleted_at.is_(None),
                MachineWorksiteAssignment.worksite_id == worksite.id,
            )
            .limit(1)
        )
        if machine is None:
            raise _not_found()
        return machine.description

    @staticmethod
    def _build_document_association(
        document_id: UUID,
        worksite_id: UUID,
        subject_kind: SubjectKind,
        subject_id: UUID,
    ) -> WorksiteDocument | ContractorDocument | PersonDocument | MachineDocument:
        common = {"organization_id": PILOT_ORGANIZATION_ID, "document_id": document_id}
        if subject_kind is SubjectKind.WORKSITE:
            return WorksiteDocument(**common, worksite_id=worksite_id)
        if subject_kind is SubjectKind.CONTRACTOR:
            return ContractorDocument(**common, contractor_id=subject_id)
        if subject_kind is SubjectKind.PERSON:
            return PersonDocument(**common, person_id=subject_id)
        return MachineDocument(**common, machine_id=subject_id)

    async def _document_subject_for_worksite(
        self,
        worksite_id: UUID,
        document_id: UUID,
    ) -> tuple[SubjectKind, UUID, str] | None:
        direct = await self.session.scalar(
            select(WorksiteDocument).where(
                WorksiteDocument.organization_id == PILOT_ORGANIZATION_ID,
                WorksiteDocument.document_id == document_id,
                WorksiteDocument.worksite_id == worksite_id,
            )
        )
        if direct is not None:
            worksite = await self._get_worksite(worksite_id)
            return SubjectKind.WORKSITE, worksite.id, worksite.name

        contractor_row = (
            await self.session.execute(
                select(ContractorDocument, Contractor)
                .join(
                    Contractor,
                    and_(
                        Contractor.organization_id == ContractorDocument.organization_id,
                        Contractor.id == ContractorDocument.contractor_id,
                    ),
                )
                .join(
                    WorksiteContractor,
                    and_(
                        WorksiteContractor.organization_id == Contractor.organization_id,
                        WorksiteContractor.contractor_id == Contractor.id,
                    ),
                )
                .where(
                    ContractorDocument.organization_id == PILOT_ORGANIZATION_ID,
                    ContractorDocument.document_id == document_id,
                    Contractor.deleted_at.is_(None),
                    WorksiteContractor.worksite_id == worksite_id,
                )
                .limit(1)
            )
        ).first()
        if contractor_row is not None:
            link, contractor = contractor_row
            return SubjectKind.CONTRACTOR, link.contractor_id, contractor.legal_name

        person_row = (
            await self.session.execute(
                select(PersonDocument, Person)
                .join(
                    Person,
                    and_(
                        Person.organization_id == PersonDocument.organization_id,
                        Person.id == PersonDocument.person_id,
                    ),
                )
                .join(
                    PersonAssignment,
                    and_(
                        PersonAssignment.organization_id == Person.organization_id,
                        PersonAssignment.person_id == Person.id,
                    ),
                )
                .where(
                    PersonDocument.organization_id == PILOT_ORGANIZATION_ID,
                    PersonDocument.document_id == document_id,
                    Person.deleted_at.is_(None),
                    PersonAssignment.worksite_id == worksite_id,
                )
                .limit(1)
            )
        ).first()
        if person_row is not None:
            link, person = person_row
            return SubjectKind.PERSON, link.person_id, person.display_name

        machine_row = (
            await self.session.execute(
                select(MachineDocument, Machine)
                .join(
                    Machine,
                    and_(
                        Machine.organization_id == MachineDocument.organization_id,
                        Machine.id == MachineDocument.machine_id,
                    ),
                )
                .join(
                    MachineWorksiteAssignment,
                    and_(
                        MachineWorksiteAssignment.organization_id == Machine.organization_id,
                        MachineWorksiteAssignment.machine_id == Machine.id,
                    ),
                )
                .where(
                    MachineDocument.organization_id == PILOT_ORGANIZATION_ID,
                    MachineDocument.document_id == document_id,
                    Machine.deleted_at.is_(None),
                    MachineWorksiteAssignment.worksite_id == worksite_id,
                )
                .limit(1)
            )
        ).first()
        if machine_row is not None:
            link, machine = machine_row
            return SubjectKind.MACHINE, link.machine_id, machine.description
        return None

    async def _contractors_for_worksite(self, worksite_id: UUID) -> list[ContractorView]:
        parent = aliased(Contractor)
        rows = (
            await self.session.execute(
                select(Contractor, WorksiteContractor, parent.legal_name)
                .join(
                    WorksiteContractor,
                    and_(
                        WorksiteContractor.organization_id == Contractor.organization_id,
                        WorksiteContractor.contractor_id == Contractor.id,
                    ),
                )
                .outerjoin(
                    parent,
                    and_(
                        parent.organization_id == WorksiteContractor.organization_id,
                        parent.id == WorksiteContractor.parent_contracting_company_id,
                    ),
                )
                .where(
                    Contractor.organization_id == PILOT_ORGANIZATION_ID,
                    Contractor.deleted_at.is_(None),
                    WorksiteContractor.worksite_id == worksite_id,
                )
                .order_by(Contractor.legal_name, WorksiteContractor.started_on)
            )
        ).all()
        return [
            self._contractor_view(contractor, assignment, parent_name)
            for contractor, assignment, parent_name in rows
        ]

    async def _functional_assignments_for_worksite(
        self, worksite_id: UUID
    ) -> list[WorksiteFunctionalAssignmentView]:
        assignments = await self.session.scalars(
            select(WorksiteFunctionalAssignment)
            .where(
                WorksiteFunctionalAssignment.organization_id == PILOT_ORGANIZATION_ID,
                WorksiteFunctionalAssignment.worksite_id == worksite_id,
            )
            .order_by(
                WorksiteFunctionalAssignment.function_code,
                WorksiteFunctionalAssignment.valid_from,
                WorksiteFunctionalAssignment.id,
            )
        )
        return [await self._functional_assignment_view(item) for item in assignments]

    async def _functional_assignment_view(
        self, assignment: WorksiteFunctionalAssignment
    ) -> WorksiteFunctionalAssignmentView:
        person = None
        if assignment.person_id is not None:
            person = await self.session.scalar(
                select(Person).where(
                    Person.organization_id == PILOT_ORGANIZATION_ID,
                    Person.id == assignment.person_id,
                )
            )
        contractor = None
        if assignment.represented_contractor_id is not None:
            contractor = await self.session.scalar(
                select(Contractor).where(
                    Contractor.organization_id == PILOT_ORGANIZATION_ID,
                    Contractor.id == assignment.represented_contractor_id,
                )
            )
        actor = next(
            (
                candidate
                for candidate in PILOT_ACTORS.values()
                if candidate.id == assignment.actor_id
            ),
            None,
        )
        profession_code = (
            person.profession_code if person else actor.profession_code if actor else None
        )
        return WorksiteFunctionalAssignmentView.model_validate(
            {
                "id": assignment.id,
                "worksite_id": assignment.worksite_id,
                "actor_id": assignment.actor_id,
                "actor_key": actor.key if actor else "legacy",
                "actor_label": actor.label if actor else "Actor sintético legado",
                "person_id": assignment.person_id,
                "person_name": person.display_name if person else None,
                "profession_code": profession_code,
                "function_code": assignment.function_code,
                "represented_contractor_id": assignment.represented_contractor_id,
                "represented_contractor_name": contractor.legal_name if contractor else None,
                "delegated_by_assignment_id": assignment.delegated_by_assignment_id,
                "permission_scope": assignment.permission_scope,
                "valid_from": assignment.valid_from,
                "valid_to": assignment.valid_to,
                "version": assignment.version,
            }
        )

    async def _people_for_worksite(self, worksite_id: UUID) -> list[PersonView]:
        rows = (
            await self.session.execute(
                select(Person, PersonAssignment)
                .join(
                    PersonAssignment,
                    and_(
                        PersonAssignment.organization_id == Person.organization_id,
                        PersonAssignment.person_id == Person.id,
                    ),
                )
                .where(
                    Person.organization_id == PILOT_ORGANIZATION_ID,
                    Person.deleted_at.is_(None),
                    PersonAssignment.worksite_id == worksite_id,
                )
                .order_by(Person.display_name, PersonAssignment.started_on)
            )
        ).all()
        result: list[PersonView] = []
        for person, assignment in rows:
            verification = await self.session.scalar(
                select(PersonVerification)
                .where(
                    PersonVerification.organization_id == PILOT_ORGANIZATION_ID,
                    PersonVerification.worksite_id == worksite_id,
                    PersonVerification.person_id == person.id,
                )
                .order_by(PersonVerification.verified_at.desc(), PersonVerification.id.desc())
                .limit(1)
            )
            result.append(self._person_view(person, assignment, verification))
        return result

    async def _machines_for_worksite(self, worksite_id: UUID) -> list[MachineView]:
        rows = (
            await self.session.execute(
                select(Machine, MachineWorksiteAssignment)
                .join(
                    MachineWorksiteAssignment,
                    and_(
                        MachineWorksiteAssignment.organization_id == Machine.organization_id,
                        MachineWorksiteAssignment.machine_id == Machine.id,
                    ),
                )
                .where(
                    Machine.organization_id == PILOT_ORGANIZATION_ID,
                    Machine.deleted_at.is_(None),
                    MachineWorksiteAssignment.worksite_id == worksite_id,
                )
                .order_by(Machine.internal_code, MachineWorksiteAssignment.started_on)
            )
        ).all()
        inspections_by_machine = await self._machine_inspections_for_worksite(
            {machine.id for machine, _assignment in rows},
            worksite_id,
        )
        inspection_ids = {
            inspection.id
            for inspections in inspections_by_machine.values()
            for inspection in inspections
        }
        validations_by_inspection = await self._machine_validations_for_inspections(inspection_ids)
        result: list[MachineView] = []
        for machine, assignment in rows:
            inspections = inspections_by_machine.get(machine.id, [])
            result.append(
                self._machine_view(
                    machine,
                    assignment,
                    inspections[0] if inspections else None,
                    inspections=inspections,
                    validations_by_inspection=validations_by_inspection,
                )
            )
        return result

    async def _machine_validations_for_inspections(
        self, inspection_ids: set[UUID]
    ) -> dict[UUID, list[MachineInspectionValidation]]:
        if not inspection_ids:
            return {}
        validations = await self.session.scalars(
            select(MachineInspectionValidation)
            .where(
                MachineInspectionValidation.organization_id == PILOT_ORGANIZATION_ID,
                MachineInspectionValidation.inspection_id.in_(inspection_ids),
            )
            .order_by(
                MachineInspectionValidation.inspection_id,
                MachineInspectionValidation.validated_at,
                MachineInspectionValidation.id,
            )
        )
        result: dict[UUID, list[MachineInspectionValidation]] = {}
        for validation in validations:
            result.setdefault(validation.inspection_id, []).append(validation)
        return result

    async def _machine_inspections_for_worksite(
        self,
        machine_ids: set[UUID],
        worksite_id: UUID,
    ) -> dict[UUID, list[MachineInspection]]:
        if not machine_ids:
            return {}
        inspections = await self.session.scalars(
            select(MachineInspection)
            .where(
                MachineInspection.organization_id == PILOT_ORGANIZATION_ID,
                MachineInspection.machine_id.in_(machine_ids),
                MachineInspection.worksite_id == worksite_id,
            )
            .order_by(
                MachineInspection.machine_id,
                MachineInspection.inspected_at.desc(),
                MachineInspection.id.desc(),
            )
        )
        result: dict[UUID, list[MachineInspection]] = {}
        for inspection in inspections:
            result.setdefault(inspection.machine_id, []).append(inspection)
        return result

    async def _stages_for_worksite(self, worksite_id: UUID) -> list[WorksiteStageView]:
        stages = await self.session.scalars(
            select(WorksiteStage)
            .where(
                WorksiteStage.organization_id == PILOT_ORGANIZATION_ID,
                WorksiteStage.worksite_id == worksite_id,
            )
            .order_by(WorksiteStage.started_on, WorksiteStage.created_at, WorksiteStage.id)
        )
        return [await self._worksite_stage_view_with_history(stage) for stage in stages]

    async def _documents_for_worksite(self, worksite: Worksite) -> list[DocumentView]:
        result: list[DocumentView] = []
        direct_rows = (
            await self.session.execute(
                select(Document, WorksiteDocument)
                .join(
                    WorksiteDocument,
                    and_(
                        WorksiteDocument.organization_id == Document.organization_id,
                        WorksiteDocument.document_id == Document.id,
                    ),
                )
                .where(
                    Document.organization_id == PILOT_ORGANIZATION_ID,
                    WorksiteDocument.worksite_id == worksite.id,
                )
            )
        ).all()
        result.extend(
            self._document_view(
                document,
                subject_kind=SubjectKind.WORKSITE,
                subject_id=link.worksite_id,
                subject_name=worksite.name,
            )
            for document, link in direct_rows
        )
        result.extend(await self._contractor_documents_for_worksite(worksite.id))
        result.extend(await self._person_documents_for_worksite(worksite.id))
        result.extend(await self._machine_documents_for_worksite(worksite.id))
        versions_by_document = await self._document_versions_for_documents(
            {document.id for document in result}
        )
        reviews_by_document = await self._document_reviews_for_documents(
            {document.id for document in result}
        )
        result = [
            document.model_copy(
                update={
                    "versions": versions_by_document.get(document.id, []),
                    "reviews": reviews_by_document.get(document.id, []),
                }
            )
            for document in result
        ]
        return sorted(result, key=lambda item: (item.title, str(item.id)))

    async def _document_versions_for_documents(
        self,
        document_ids: set[UUID],
    ) -> dict[UUID, list[DocumentVersionView]]:
        if not document_ids:
            return {}
        versions = await self.session.scalars(
            select(DocumentVersion)
            .where(
                DocumentVersion.organization_id == PILOT_ORGANIZATION_ID,
                DocumentVersion.document_id.in_(document_ids),
            )
            .order_by(
                DocumentVersion.document_id,
                DocumentVersion.version_number.desc(),
            )
        )
        result: dict[UUID, list[DocumentVersionView]] = {}
        for version in versions:
            result.setdefault(version.document_id, []).append(self._document_version_view(version))
        return result

    async def _document_reviews_for_documents(
        self, document_ids: set[UUID]
    ) -> dict[UUID, list[DocumentReviewView]]:
        if not document_ids:
            return {}
        reviews = await self.session.scalars(
            select(DocumentReview)
            .where(
                DocumentReview.organization_id == PILOT_ORGANIZATION_ID,
                DocumentReview.document_id.in_(document_ids),
            )
            .order_by(
                DocumentReview.document_id,
                DocumentReview.reviewed_at.desc(),
                DocumentReview.id.desc(),
            )
        )
        result: dict[UUID, list[DocumentReviewView]] = {}
        for review in reviews:
            result.setdefault(review.document_id, []).append(self._document_review_view(review))
        return result

    async def _contractor_documents_for_worksite(self, worksite_id: UUID) -> list[DocumentView]:
        rows = (
            await self.session.execute(
                select(Document, ContractorDocument, Contractor)
                .join(
                    ContractorDocument,
                    and_(
                        ContractorDocument.organization_id == Document.organization_id,
                        ContractorDocument.document_id == Document.id,
                    ),
                )
                .join(
                    Contractor,
                    and_(
                        Contractor.organization_id == ContractorDocument.organization_id,
                        Contractor.id == ContractorDocument.contractor_id,
                    ),
                )
                .join(
                    WorksiteContractor,
                    and_(
                        WorksiteContractor.organization_id == Contractor.organization_id,
                        WorksiteContractor.contractor_id == Contractor.id,
                    ),
                )
                .where(
                    Document.organization_id == PILOT_ORGANIZATION_ID,
                    WorksiteContractor.worksite_id == worksite_id,
                )
                .distinct()
            )
        ).all()
        return [
            self._document_view(
                document,
                subject_kind=SubjectKind.CONTRACTOR,
                subject_id=link.contractor_id,
                subject_name=contractor.legal_name,
            )
            for document, link, contractor in rows
        ]

    async def _person_documents_for_worksite(self, worksite_id: UUID) -> list[DocumentView]:
        rows = (
            await self.session.execute(
                select(Document, PersonDocument, Person)
                .join(
                    PersonDocument,
                    and_(
                        PersonDocument.organization_id == Document.organization_id,
                        PersonDocument.document_id == Document.id,
                    ),
                )
                .join(
                    Person,
                    and_(
                        Person.organization_id == PersonDocument.organization_id,
                        Person.id == PersonDocument.person_id,
                    ),
                )
                .join(
                    PersonAssignment,
                    and_(
                        PersonAssignment.organization_id == Person.organization_id,
                        PersonAssignment.person_id == Person.id,
                    ),
                )
                .where(
                    Document.organization_id == PILOT_ORGANIZATION_ID,
                    PersonAssignment.worksite_id == worksite_id,
                )
                .distinct()
            )
        ).all()
        return [
            self._document_view(
                document,
                subject_kind=SubjectKind.PERSON,
                subject_id=link.person_id,
                subject_name=person.display_name,
            )
            for document, link, person in rows
        ]

    async def _machine_documents_for_worksite(self, worksite_id: UUID) -> list[DocumentView]:
        rows = (
            await self.session.execute(
                select(Document, MachineDocument, Machine)
                .join(
                    MachineDocument,
                    and_(
                        MachineDocument.organization_id == Document.organization_id,
                        MachineDocument.document_id == Document.id,
                    ),
                )
                .join(
                    Machine,
                    and_(
                        Machine.organization_id == MachineDocument.organization_id,
                        Machine.id == MachineDocument.machine_id,
                    ),
                )
                .join(
                    MachineWorksiteAssignment,
                    and_(
                        MachineWorksiteAssignment.organization_id == Machine.organization_id,
                        MachineWorksiteAssignment.machine_id == Machine.id,
                    ),
                )
                .where(
                    Document.organization_id == PILOT_ORGANIZATION_ID,
                    MachineWorksiteAssignment.worksite_id == worksite_id,
                )
                .distinct()
            )
        ).all()
        return [
            self._document_view(
                document,
                subject_kind=SubjectKind.MACHINE,
                subject_id=link.machine_id,
                subject_name=machine.description,
            )
            for document, link, machine in rows
        ]

    async def _audits_for_worksite(self, worksite_id: UUID) -> list[AuditView]:
        audits = await self.session.scalars(
            select(Audit)
            .where(
                Audit.organization_id == PILOT_ORGANIZATION_ID,
                Audit.worksite_id == worksite_id,
            )
            .order_by(Audit.started_at.desc(), Audit.id.desc())
        )
        return [await self._audit_view(audit) for audit in audits]

    async def _findings_for_worksite(self, worksite_id: UUID) -> list[FindingView]:
        findings = await self.session.scalars(
            select(Finding)
            .where(
                Finding.organization_id == PILOT_ORGANIZATION_ID,
                Finding.worksite_id == worksite_id,
            )
            .order_by(Finding.created_at.desc(), Finding.id.desc())
        )
        return [await self._finding_view(finding) for finding in findings]

    async def _audit_view(self, audit: Audit) -> AuditView:
        rows = (
            await self.session.execute(
                select(AuditControl, FindingControl.finding_id)
                .outerjoin(
                    FindingControl,
                    and_(
                        FindingControl.organization_id == AuditControl.organization_id,
                        FindingControl.audit_control_id == AuditControl.id,
                    ),
                )
                .where(
                    AuditControl.organization_id == PILOT_ORGANIZATION_ID,
                    AuditControl.audit_id == audit.id,
                )
                .order_by(AuditControl.recorded_at, AuditControl.id)
            )
        ).all()
        controls = [self._audit_control_view(control, finding_id) for control, finding_id in rows]
        catalog_controls = await self._catalog_controls_for_audit(audit)
        auditor_assignment = None
        if audit.auditor_assignment_id is not None:
            auditor_assignment = await self.session.scalar(
                select(WorksiteFunctionalAssignment).where(
                    WorksiteFunctionalAssignment.organization_id == PILOT_ORGANIZATION_ID,
                    WorksiteFunctionalAssignment.id == audit.auditor_assignment_id,
                )
            )
        auditor_person_name = None
        if auditor_assignment is not None and auditor_assignment.person_id is not None:
            auditor_person_name = await self.session.scalar(
                select(Person.display_name).where(
                    Person.organization_id == PILOT_ORGANIZATION_ID,
                    Person.id == auditor_assignment.person_id,
                )
            )
        responsible_professional_name = None
        if audit.associated_professional_person_id is not None:
            responsible_professional_name = await self.session.scalar(
                select(Person.display_name).where(
                    Person.organization_id == PILOT_ORGANIZATION_ID,
                    Person.id == audit.associated_professional_person_id,
                )
            )
        actor = next(
            (
                candidate
                for candidate in PILOT_ACTORS.values()
                if candidate.id == audit.auditor_actor_id
            ),
            None,
        )
        return AuditView.model_validate(
            {
                "id": audit.id,
                "status": audit.status,
                "author_id": audit.author_actor_id,
                "editor_id": audit.editor_actor_id,
                "worksite_id": audit.worksite_id,
                "auditor_actor_id": audit.auditor_actor_id,
                "auditor_assignment_id": audit.auditor_assignment_id,
                "associated_professional_person_id": audit.associated_professional_person_id,
                "audit_date": audit.audit_date,
                "started_at": audit.started_at,
                "finalized_at": audit.finalized_at,
                "available_controls": [
                    self._audit_catalog_control_view(catalog) for catalog in catalog_controls
                ],
                "controls": controls,
                "auditor_name": auditor_person_name or (actor.label if actor else None),
                "auditor_function": (
                    auditor_assignment.function_code if auditor_assignment is not None else None
                ),
                "responsible_professional_name": responsible_professional_name,
            }
        )

    async def _catalog_controls_for_audit(self, audit: Audit) -> list[ControlCatalogVersion]:
        catalog_anchor = await self.session.scalar(
            select(ControlCatalogVersion).where(
                ControlCatalogVersion.organization_id == PILOT_ORGANIZATION_ID,
                ControlCatalogVersion.id == audit.control_catalog_version_id,
                ControlCatalogVersion.code.like("SYN-%"),
                ControlCatalogVersion.published_at.is_not(None),
            )
        )
        if catalog_anchor is None:
            raise _conflict(
                "pilot_catalog_unavailable",
                "El catálogo sintético asociado a la auditoría ya no está disponible.",
            )
        catalog_controls = await self.session.scalars(
            select(ControlCatalogVersion)
            .where(
                ControlCatalogVersion.organization_id == PILOT_ORGANIZATION_ID,
                ControlCatalogVersion.code.like("SYN-%"),
                ControlCatalogVersion.version_number == catalog_anchor.version_number,
                ControlCatalogVersion.published_at == catalog_anchor.published_at,
            )
            .order_by(ControlCatalogVersion.code, ControlCatalogVersion.id)
        )
        return list(catalog_controls)

    async def _finding_view(self, finding: Finding) -> FindingView:
        link = await self.session.scalar(
            select(FindingControl).where(
                FindingControl.organization_id == PILOT_ORGANIZATION_ID,
                FindingControl.finding_id == finding.id,
            )
        )
        affected_contractor_name = None
        if finding.affected_contractor_id is not None:
            affected_contractor_name = await self.session.scalar(
                select(Contractor.legal_name).where(
                    Contractor.organization_id == PILOT_ORGANIZATION_ID,
                    Contractor.id == finding.affected_contractor_id,
                )
            )
        responsible_contractor_name = None
        if finding.responsible_contractor_id is not None:
            responsible_contractor_name = await self.session.scalar(
                select(Contractor.legal_name).where(
                    Contractor.organization_id == PILOT_ORGANIZATION_ID,
                    Contractor.id == finding.responsible_contractor_id,
                )
            )
        responsible_person_name = None
        if finding.responsible_person_id is not None:
            responsible_person_name = await self.session.scalar(
                select(Person.display_name).where(
                    Person.organization_id == PILOT_ORGANIZATION_ID,
                    Person.id == finding.responsible_person_id,
                )
            )
        corrections = await self.session.scalars(
            select(Correction)
            .where(
                Correction.organization_id == PILOT_ORGANIZATION_ID,
                Correction.finding_id == finding.id,
            )
            .order_by(Correction.created_at, Correction.id)
        )
        verifications = await self.session.scalars(
            select(Verification)
            .where(
                Verification.organization_id == PILOT_ORGANIZATION_ID,
                Verification.finding_id == finding.id,
            )
            .order_by(Verification.created_at, Verification.id)
        )
        return FindingView.model_validate(
            {
                "id": finding.id,
                "audit_id": finding.audit_id,
                "audit_control_id": link.audit_control_id if link else None,
                "title": finding.title,
                "description": finding.description,
                "severity_code": finding.severity_code,
                "status": finding.status,
                "due_at": finding.due_at,
                "overdue": finding.status != "CERRADO" and finding.due_at < _utc_now(),
                "closed_at": finding.closed_at,
                "created_by": finding.created_by_actor_id,
                "created_at": finding.created_at,
                "affected_contractor_id": finding.affected_contractor_id,
                "affected_contractor_name": affected_contractor_name,
                "responsible_contractor_id": finding.responsible_contractor_id,
                "responsible_contractor_name": responsible_contractor_name,
                "responsible_person_id": finding.responsible_person_id,
                "responsible_person_name": responsible_person_name,
                "corrections": [self._correction_view(row) for row in corrections],
                "verifications": [self._verification_view(row) for row in verifications],
                "events": await self._events_for_finding(finding.id),
                "source_label": (
                    "Control de auditoría"
                    if link is not None
                    else "Persona no registrada en obra"
                    if finding.title == "Persona no registrada en obra"
                    else "Hallazgo manual"
                ),
            }
        )

    async def _events_for_finding(self, finding_id: UUID) -> list[FindingEventView]:
        events = await self.session.scalars(
            select(FindingEvent)
            .where(
                FindingEvent.organization_id == PILOT_ORGANIZATION_ID,
                FindingEvent.finding_id == finding_id,
            )
            .order_by(FindingEvent.created_at, FindingEvent.id)
        )
        return [self._event_view(event) for event in events]

    async def _latest_correction(self, finding_id: UUID) -> Correction | None:
        return cast(
            Correction | None,
            await self.session.scalar(
                select(Correction)
                .where(
                    Correction.organization_id == PILOT_ORGANIZATION_ID,
                    Correction.finding_id == finding_id,
                )
                .order_by(Correction.created_at.desc(), Correction.id.desc())
                .limit(1)
            ),
        )

    @staticmethod
    def _worksite_summary(worksite: Worksite) -> WorksiteSummary:
        return WorksiteSummary.model_validate(
            {
                "id": worksite.id,
                "code": worksite.code,
                "name": worksite.name,
                "jurisdiction": worksite.jurisdiction,
                "country": worksite.country,
                "province": worksite.province,
                "municipality": worksite.municipality,
                "status": worksite.status,
                "version": worksite.version,
                "created_at": worksite.created_at,
                "updated_at": worksite.updated_at,
            }
        )

    @staticmethod
    def _worksite_stage_view(stage: WorksiteStage) -> WorksiteStageView:
        return WorksiteStageView.model_validate(
            {
                "id": stage.id,
                "worksite_id": stage.worksite_id,
                "code": stage.code,
                "name": stage.name,
                "started_on": stage.started_on,
                "ended_on": stage.ended_on,
                "sector": stage.sector,
                "notes": stage.notes,
                "created_at": stage.created_at,
                "updated_at": stage.updated_at,
                "status": getattr(stage, "status", None) or "ACTIVA",
            }
        )

    async def _worksite_stage_view_with_history(self, stage: WorksiteStage) -> WorksiteStageView:
        events = await self.session.scalars(
            select(WorksiteStageEvent)
            .where(
                WorksiteStageEvent.organization_id == PILOT_ORGANIZATION_ID,
                WorksiteStageEvent.stage_id == stage.id,
            )
            .order_by(WorksiteStageEvent.created_at, WorksiteStageEvent.id)
        )
        view = self._worksite_stage_view(stage)
        return view.model_copy(
            update={
                "history": [
                    WorksiteStageEventView.model_validate(
                        {
                            "id": event.id,
                            "event_type": event.event_type,
                            "actor_id": event.actor_id,
                            "detail": event.detail,
                            "created_at": event.created_at,
                        }
                    )
                    for event in events
                ]
            }
        )

    @staticmethod
    def _contractor_view(
        contractor: Contractor,
        assignment: WorksiteContractor,
        parent_name: str | None = None,
    ) -> ContractorView:
        return ContractorView.model_validate(
            {
                "id": contractor.id,
                "assignment_id": assignment.id,
                "legal_name": contractor.legal_name,
                "trade": contractor.trade,
                "started_on": assignment.started_on,
                "ended_on": assignment.ended_on,
                "participation_type": assignment.participation_type or "CONTRACTOR",
                "parent_contracting_company_id": assignment.parent_contracting_company_id,
                "parent_contracting_company_name": parent_name,
            }
        )

    @staticmethod
    def _person_view(
        person: Person,
        assignment: PersonAssignment,
        verification: PersonVerification | None = None,
    ) -> PersonView:
        return PersonView.model_validate(
            {
                "id": person.id,
                "assignment_id": assignment.id,
                "display_name": person.display_name,
                "contractor_id": assignment.contractor_id,
                "role_label": person.role_label,
                "profession_code": person.profession_code or "OTRA",
                "started_on": assignment.started_on,
                "ended_on": assignment.ended_on,
                "habilitation_status": verification.status
                if verification
                else "PENDIENTE_VERIFICACION",
                "habilitation_verified_by": verification.verified_by_actor_id
                if verification
                else None,
                "habilitation_verified_at": verification.verified_at if verification else None,
                "habilitation_observation": verification.observation if verification else None,
            }
        )

    @staticmethod
    def _document_version_view(version: DocumentVersion) -> DocumentVersionView:
        return DocumentVersionView.model_validate(
            {
                "id": version.id,
                "version_number": version.version_number,
                "title": version.title,
                "document_type": version.document_type,
                "review_status": version.review_status,
                "valid_from": version.valid_from,
                "expires_on": version.expires_on,
                "notes": version.notes,
                "actor_id": version.actor_id,
                "created_at": version.created_at,
            }
        )

    @staticmethod
    def _document_view(
        document: Document,
        *,
        subject_kind: SubjectKind,
        subject_id: UUID,
        subject_name: str,
        versions: list[DocumentVersionView] | None = None,
        reviews: list[DocumentReviewView] | None = None,
    ) -> DocumentView:
        return DocumentView.model_validate(
            {
                "id": document.id,
                "subject_kind": subject_kind,
                "subject_id": subject_id,
                "subject_name": subject_name,
                "version": document.version,
                "title": document.title,
                "document_type": document.document_type,
                "review_status": document.review_status,
                "status": derive_document_status(
                    document.review_status,
                    document.expires_on,
                    today=_today_in_argentina(),
                ),
                "valid_from": document.valid_from,
                "expires_on": document.expires_on,
                "notes": document.notes,
                "created_at": document.created_at,
                "versions": versions or [],
                "uploaded_by": document.uploaded_by_actor_id,
                "uploaded_at": document.uploaded_at,
                "reviews": reviews or [],
            }
        )

    @staticmethod
    def _document_review_view(review: DocumentReview) -> DocumentReviewView:
        return DocumentReviewView.model_validate(
            {
                "id": review.id,
                "reviewer": review.reviewer_actor_id,
                "reviewer_function": review.reviewer_function,
                "reviewed_at": review.reviewed_at,
                "result": review.result,
                "foundation": review.foundation,
            }
        )

    @staticmethod
    def _machine_view(
        machine: Machine,
        assignment: MachineWorksiteAssignment,
        inspection: MachineInspection | None,
        *,
        inspections: list[MachineInspection] | None = None,
        validations_by_inspection: dict[UUID, list[MachineInspectionValidation]] | None = None,
    ) -> MachineView:
        return MachineView.model_validate(
            {
                "id": machine.id,
                "assignment_id": assignment.id,
                "internal_code": machine.internal_code,
                "description": machine.description,
                "status": machine.status,
                "version": machine.version,
                "contractor_id": assignment.contractor_id,
                "inspection_reason": inspection.reason if inspection else None,
                "inspected_at": inspection.inspected_at if inspection else None,
                "started_on": assignment.started_on,
                "ended_on": assignment.ended_on,
                "inspections": [
                    PilotService._machine_inspection_view(
                        item,
                        (validations_by_inspection or {}).get(item.id, []),
                    )
                    for item in (inspections or ([inspection] if inspection else []))
                ],
                "machine_type": machine.machine_type,
                "brand": machine.brand,
                "model": machine.model,
                "license_plate": machine.license_plate,
                "operator_person_id": machine.operator_person_id,
            }
        )

    @staticmethod
    def _machine_inspection_view(
        inspection: MachineInspection,
        validations: list[MachineInspectionValidation] | None = None,
    ) -> MachineInspectionView:
        return MachineInspectionView.model_validate(
            {
                "id": inspection.id,
                "resulting_status": inspection.resulting_status,
                "reason": inspection.reason,
                "actor_id": inspection.actor_id,
                "inspected_at": inspection.inspected_at,
                "checklist": inspection.checklist or {},
                "evidence_note": inspection.evidence_note,
                "inspector_function": inspection.inspector_function,
                "validations": [
                    {
                        "id": validation.id,
                        "validated_by": validation.validated_by_actor_id,
                        "validator_function": validation.validator_function,
                        "notes": validation.notes,
                        "validated_at": validation.validated_at,
                    }
                    for validation in validations or []
                ],
            }
        )

    @staticmethod
    def _audit_control_view(
        control: AuditControl,
        finding_id: UUID | None,
    ) -> AuditControlView:
        return AuditControlView.model_validate(
            {
                "id": control.id,
                "catalog_code": control.catalog_code,
                "catalog_title": control.catalog_title,
                "result": control.result,
                "reason": control.reason,
                "finding_id": finding_id,
            }
        )

    @staticmethod
    def _audit_catalog_control_view(catalog: ControlCatalogVersion) -> dict[str, str]:
        return {
            "catalog_code": catalog.code,
            "catalog_title": catalog.title,
        }

    @staticmethod
    def _correction_view(correction: Correction) -> CorrectionView:
        return CorrectionView.model_validate(
            {
                "id": correction.id,
                "description": correction.description,
                "evidence_note": correction.evidence_note,
                "created_by": correction.authored_by_actor_id,
                "created_at": correction.created_at,
            }
        )

    @staticmethod
    def _verification_view(verification: Verification) -> VerificationView:
        return VerificationView.model_validate(
            {
                "id": verification.id,
                "decision": verification.decision,
                "notes": verification.notes,
                "verified_by": verification.verified_by_actor_id,
                "created_at": verification.created_at,
            }
        )

    @staticmethod
    def _event_view(event: FindingEvent) -> FindingEventView:
        return FindingEventView.model_validate(
            {
                "id": event.id,
                "event_type": event.event_type,
                "from_status": event.from_status,
                "to_status": event.to_status,
                "detail": event.detail,
                "actor_id": event.actor_id,
                "created_at": event.created_at,
            }
        )


async def get_pilot_service(
    context: Annotated[PilotRequestContext, Depends(get_pilot_context)],
) -> PilotService:
    return PilotService(context)
