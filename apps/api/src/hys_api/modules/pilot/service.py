"""Casos de uso transaccionales del primer flujo vertical sintético."""

from datetime import UTC, date, datetime, timedelta, timezone, tzinfo
from functools import lru_cache
from typing import Annotated, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from hys_api.api.dependencies import (
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
    DocumentVersion,
    Finding,
    FindingControl,
    FindingEvent,
    Machine,
    MachineDocument,
    MachineInspection,
    MachineWorksiteAssignment,
    Person,
    PersonAssignment,
    PersonDocument,
    SeverityCatalogVersion,
    Verification,
    WorksiteContractor,
    WorksiteDocument,
    WorksiteStage,
)
from hys_api.modules.pilot.schemas import (
    AuditControlCreate,
    AuditControlMutationResponse,
    AuditControlView,
    AuditView,
    ContractorCreate,
    ContractorView,
    CorrectionCreate,
    CorrectionView,
    DocumentCreate,
    DocumentVersionCreate,
    DocumentVersionView,
    DocumentView,
    FindingEventView,
    FindingTimeline,
    FindingView,
    MachineCreate,
    MachineInspectionCreate,
    MachineInspectionView,
    MachineView,
    PersonCreate,
    PersonView,
    SubjectKind,
    VerificationCreate,
    VerificationDecision,
    VerificationView,
    WorksiteCreate,
    WorksiteDetail,
    WorksiteStageCreate,
    WorksiteStageView,
    WorksiteSummary,
    derive_document_status,
    derive_worksite_metrics,
)
from hys_api.modules.worksites.models import Worksite


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
        rows = await self.session.scalars(
            select(Worksite)
            .where(
                Worksite.organization_id == PILOT_ORGANIZATION_ID,
                Worksite.deleted_at.is_(None),
            )
            .order_by(Worksite.code, Worksite.id)
        )
        return [self._worksite_summary(row) for row in rows]

    async def create_worksite(self, payload: WorksiteCreate) -> WorksiteSummary:
        self._require_resource_write()
        worksite = Worksite(
            organization_id=PILOT_ORGANIZATION_ID,
            code=payload.code,
            name=payload.name,
            jurisdiction=payload.jurisdiction,
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
        contractors = await self._contractors_for_worksite(worksite_id)
        people = await self._people_for_worksite(worksite_id)
        documents = await self._documents_for_worksite(worksite)
        machines = await self._machines_for_worksite(worksite_id)
        stages = await self._stages_for_worksite(worksite_id)
        audits = await self._audits_for_worksite(worksite_id)
        findings = await self._findings_for_worksite(worksite_id)
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
        return self._worksite_stage_view(stage)

    async def create_contractor(
        self,
        worksite_id: UUID,
        payload: ContractorCreate,
    ) -> ContractorView:
        self._require_resource_write()
        await self._get_active_worksite(worksite_id)
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
        await self._get_active_worksite(worksite_id)
        started_on = payload.started_on or _today_in_argentina()
        await self._get_contractor_for_worksite(
            worksite_id,
            payload.contractor_id,
            on_date=started_on,
        )
        person = Person(
            organization_id=PILOT_ORGANIZATION_ID,
            display_name=payload.display_name,
            role_label=payload.role_label,
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

    async def create_document(
        self,
        worksite_id: UUID,
        payload: DocumentCreate,
    ) -> DocumentView:
        self._require_resource_write()
        worksite = await self._get_active_worksite(worksite_id)
        subject_name = await self._validate_document_subject(worksite, payload)
        document = Document(
            organization_id=PILOT_ORGANIZATION_ID,
            title=payload.title,
            document_type=payload.document_type,
            review_status=payload.review_status.value,
            valid_from=payload.valid_from,
            expires_on=payload.expires_on,
            notes=payload.notes,
        )
        self.session.add(document)
        await self.session.flush()
        document_version = DocumentVersion(
            organization_id=PILOT_ORGANIZATION_ID,
            document_id=document.id,
            version_number=1,
            title=payload.title,
            document_type=payload.document_type,
            review_status=payload.review_status.value,
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

        next_version = document.version + 1
        document.title = payload.title
        document.document_type = payload.document_type
        document.review_status = payload.review_status.value
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
            review_status=payload.review_status.value,
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
        machine = Machine(
            organization_id=PILOT_ORGANIZATION_ID,
            internal_code=payload.internal_code,
            description=payload.description,
            status=payload.status.value,
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
        inspection = MachineInspection(
            organization_id=PILOT_ORGANIZATION_ID,
            machine_id=machine.id,
            worksite_id=worksite_id,
            resulting_status=payload.status.value,
            reason=payload.reason,
            actor_id=self.context.actor.id,
        )
        self.session.add_all([assignment, inspection])
        await self._flush_or_conflict(
            "machine_assignment_conflict",
            "No se pudo asignar e inspeccionar la maquinaria sintética.",
        )
        await self.session.refresh(machine)
        await self.session.refresh(assignment)
        await self.session.refresh(inspection)
        return self._machine_view(machine, assignment, inspection)

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

        machine.status = payload.resulting_status.value
        machine.version += 1
        inspection = MachineInspection(
            organization_id=PILOT_ORGANIZATION_ID,
            machine_id=machine.id,
            worksite_id=worksite_id,
            resulting_status=payload.resulting_status.value,
            reason=payload.reason,
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

    async def start_audit(self, worksite_id: UUID) -> AuditView:
        self._require_audit_write()
        await self._get_active_worksite(worksite_id)
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
            author_actor_id=self.context.actor.id,
            editor_actor_id=self.context.actor.id,
            control_catalog_version_id=catalog.id,
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
        self._require_audit_write()
        audit = await self._get_audit(audit_id, for_update=True)
        self._require_audit_editor(audit)
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
        self._require_audit_write()
        audit = await self._get_audit(audit_id, for_update=True)
        self._require_audit_editor(audit)
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
        require_pilot_role(self.context.actor, PilotRole.RESPONSABLE_HYS)
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
        if self.context.actor.id in {
            finding.created_by_actor_id,
            correction.authored_by_actor_id,
        }:
            raise _conflict(
                "segregation_of_duties",
                "El creador del desvío o autor de la corrección no puede verificarla.",
            )
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

    def _require_audit_write(self) -> None:
        require_pilot_role(
            self.context.actor,
            PilotRole.AUDITOR,
            PilotRole.RESPONSABLE_HYS,
        )

    def _require_correction_write(self) -> None:
        require_pilot_role(
            self.context.actor,
            PilotRole.TECNICO,
            PilotRole.AUDITOR,
            PilotRole.RESPONSABLE_HYS,
        )

    def _require_audit_editor(self, audit: Audit) -> None:
        if audit.editor_actor_id != self.context.actor.id:
            raise ProblemException(
                status=403,
                code="audit_editor_required",
                title="Acceso denegado",
                detail="Sólo el editor de la auditoría puede modificarla o finalizarla.",
            )

    async def _flush_or_conflict(self, code: str, detail: str) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise _conflict(code, detail) from exc

    async def _get_worksite(self, worksite_id: UUID, *, for_update: bool = False) -> Worksite:
        statement = select(Worksite).where(
            Worksite.organization_id == PILOT_ORGANIZATION_ID,
            Worksite.id == worksite_id,
            Worksite.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        worksite = await self.session.scalar(statement)
        if worksite is None:
            raise _not_found()
        return worksite

    async def _get_active_worksite(
        self,
        worksite_id: UUID,
        *,
        for_update: bool = False,
    ) -> Worksite:
        worksite = await self._get_worksite(worksite_id, for_update=for_update)
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
        rows = (
            await self.session.execute(
                select(Contractor, WorksiteContractor)
                .join(
                    WorksiteContractor,
                    and_(
                        WorksiteContractor.organization_id == Contractor.organization_id,
                        WorksiteContractor.contractor_id == Contractor.id,
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
        return [self._contractor_view(contractor, assignment) for contractor, assignment in rows]

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
        return [self._person_view(person, assignment) for person, assignment in rows]

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
        result: list[MachineView] = []
        for machine, assignment in rows:
            inspections = inspections_by_machine.get(machine.id, [])
            if inspections:
                result.append(
                    self._machine_view(
                        machine,
                        assignment,
                        inspections[0],
                        inspections=inspections,
                    )
                )
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
        return [self._worksite_stage_view(stage) for stage in stages]

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
        result = [
            document.model_copy(update={"versions": versions_by_document.get(document.id, [])})
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
        return AuditView.model_validate(
            {
                "id": audit.id,
                "status": audit.status,
                "author_id": audit.author_actor_id,
                "editor_id": audit.editor_actor_id,
                "started_at": audit.started_at,
                "finalized_at": audit.finalized_at,
                "available_controls": [
                    self._audit_catalog_control_view(catalog) for catalog in catalog_controls
                ],
                "controls": controls,
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
        if link is None:
            raise _conflict(
                "finding_without_control",
                "El desvío no conserva su vínculo con el control de origen.",
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
                "audit_control_id": link.audit_control_id,
                "title": finding.title,
                "description": finding.description,
                "severity_code": finding.severity_code,
                "status": finding.status,
                "due_at": finding.due_at,
                "overdue": finding.status != "CERRADO" and finding.due_at < _utc_now(),
                "closed_at": finding.closed_at,
                "created_by": finding.created_by_actor_id,
                "corrections": [self._correction_view(row) for row in corrections],
                "verifications": [self._verification_view(row) for row in verifications],
                "events": await self._events_for_finding(finding.id),
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
            }
        )

    @staticmethod
    def _contractor_view(
        contractor: Contractor,
        assignment: WorksiteContractor,
    ) -> ContractorView:
        return ContractorView.model_validate(
            {
                "id": contractor.id,
                "assignment_id": assignment.id,
                "legal_name": contractor.legal_name,
                "trade": contractor.trade,
                "started_on": assignment.started_on,
                "ended_on": assignment.ended_on,
            }
        )

    @staticmethod
    def _person_view(person: Person, assignment: PersonAssignment) -> PersonView:
        return PersonView.model_validate(
            {
                "id": person.id,
                "assignment_id": assignment.id,
                "display_name": person.display_name,
                "contractor_id": assignment.contractor_id,
                "role_label": person.role_label,
                "started_on": assignment.started_on,
                "ended_on": assignment.ended_on,
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
            }
        )

    @staticmethod
    def _machine_view(
        machine: Machine,
        assignment: MachineWorksiteAssignment,
        inspection: MachineInspection,
        *,
        inspections: list[MachineInspection] | None = None,
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
                "inspection_reason": inspection.reason,
                "inspected_at": inspection.inspected_at,
                "started_on": assignment.started_on,
                "ended_on": assignment.ended_on,
                "inspections": [
                    PilotService._machine_inspection_view(item)
                    for item in (inspections or [inspection])
                ],
            }
        )

    @staticmethod
    def _machine_inspection_view(inspection: MachineInspection) -> MachineInspectionView:
        return MachineInspectionView.model_validate(
            {
                "id": inspection.id,
                "resulting_status": inspection.resulting_status,
                "reason": inspection.reason,
                "actor_id": inspection.actor_id,
                "inspected_at": inspection.inspected_at,
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
