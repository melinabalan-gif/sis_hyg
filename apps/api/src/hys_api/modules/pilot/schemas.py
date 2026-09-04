"""Schemas HTTP estrictos del primer flujo vertical del piloto."""

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StringConstraints, model_validator

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
Code = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[A-Z0-9][A-Z0-9._-]*$"
    ),
]


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class SubjectKind(StrEnum):
    WORKSITE = "WORKSITE"
    CONTRACTOR = "CONTRACTOR"
    PERSON = "PERSON"
    MACHINE = "MACHINE"


class DocumentReviewStatus(StrEnum):
    PENDIENTE = "PENDIENTE"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"


class DocumentDisplayStatus(StrEnum):
    PENDIENTE = "PENDIENTE"
    RECHAZADO = "RECHAZADO"
    FALTANTE = "FALTANTE"
    VENCIDO = "VENCIDO"
    POR_VENCER = "POR_VENCER"
    VIGENTE = "VIGENTE"


class MachineStatus(StrEnum):
    OPERATIVA = "OPERATIVA"
    CON_OBSERVACIONES = "CON_OBSERVACIONES"
    FUERA_DE_SERVICIO = "FUERA_DE_SERVICIO"


class AuditStatus(StrEnum):
    EN_CURSO = "EN_CURSO"
    FINALIZADA = "FINALIZADA"


class ControlResult(StrEnum):
    CUMPLE = "CUMPLE"
    NO_CUMPLE = "NO_CUMPLE"
    NO_APLICA = "NO_APLICA"
    NO_VERIFICADO = "NO_VERIFICADO"


class FindingStatus(StrEnum):
    ABIERTO = "ABIERTO"
    EN_CORRECCION = "EN_CORRECCION"
    PENDIENTE_VERIFICACION = "PENDIENTE_VERIFICACION"
    CERRADO = "CERRADO"


class VerificationDecision(StrEnum):
    ACEPTADA = "ACEPTADA"
    RECHAZADA = "RECHAZADA"


class WorksiteCreate(StrictSchema):
    code: Code
    name: ShortText
    jurisdiction: ShortText


class WorksiteSummary(StrictSchema):
    id: UUID
    code: str
    name: str
    jurisdiction: str
    status: Literal["ACTIVE", "ARCHIVED"]
    version: int
    created_at: datetime
    updated_at: datetime


class DatedAssignmentCreate(StrictSchema):
    started_on: date | None = None
    ended_on: date | None = None

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if self.started_on is not None and self.ended_on is not None:
            if self.ended_on <= self.started_on:
                raise ValueError("ended_on debe ser posterior a started_on")
        return self


class ContractorCreate(DatedAssignmentCreate):
    legal_name: ShortText
    trade: ShortText


class ContractorView(StrictSchema):
    id: UUID
    assignment_id: UUID
    legal_name: str
    trade: str
    started_on: date
    ended_on: date | None


class PersonCreate(DatedAssignmentCreate):
    display_name: ShortText
    contractor_id: UUID
    role_label: ShortText = "Personal"


class PersonView(StrictSchema):
    id: UUID
    assignment_id: UUID
    display_name: str
    contractor_id: UUID
    role_label: str
    started_on: date
    ended_on: date | None


class DocumentCreate(StrictSchema):
    subject_kind: SubjectKind
    subject_id: UUID
    title: ShortText
    document_type: ShortText
    review_status: DocumentReviewStatus = DocumentReviewStatus.PENDIENTE
    valid_from: date | None = None
    expires_on: date | None = None
    notes: LongText | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.valid_from is not None and self.expires_on is not None:
            if self.expires_on < self.valid_from:
                raise ValueError("expires_on no puede ser anterior a valid_from")
        return self


class DocumentVersionCreate(StrictSchema):
    title: ShortText
    document_type: ShortText
    review_status: DocumentReviewStatus = DocumentReviewStatus.PENDIENTE
    valid_from: date | None = None
    expires_on: date | None = None
    notes: LongText | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.valid_from is not None and self.expires_on is not None:
            if self.expires_on < self.valid_from:
                raise ValueError("expires_on no puede ser anterior a valid_from")
        return self


class DocumentVersionView(StrictSchema):
    id: UUID
    version_number: int
    title: str
    document_type: str
    review_status: DocumentReviewStatus
    valid_from: date | None
    expires_on: date | None
    notes: str | None
    actor_id: UUID
    created_at: datetime


class DocumentView(StrictSchema):
    id: UUID
    subject_kind: SubjectKind
    subject_id: UUID
    subject_name: str
    version: int
    title: str
    document_type: str
    review_status: DocumentReviewStatus
    status: DocumentDisplayStatus
    valid_from: date | None
    expires_on: date | None
    notes: str | None
    created_at: datetime
    versions: list[DocumentVersionView] = Field(default_factory=list)


class MachineCreate(DatedAssignmentCreate):
    internal_code: Code
    description: ShortText
    status: MachineStatus
    reason: LongText
    contractor_id: UUID | None = None


class MachineInspectionCreate(StrictSchema):
    resulting_status: MachineStatus = Field(
        validation_alias=AliasChoices("resulting_status", "status")
    )
    reason: LongText


class MachineInspectionView(StrictSchema):
    id: UUID
    resulting_status: MachineStatus
    reason: str
    actor_id: UUID
    inspected_at: datetime


class MachineView(StrictSchema):
    id: UUID
    assignment_id: UUID
    internal_code: str
    description: str
    status: MachineStatus
    version: int
    contractor_id: UUID | None
    inspection_reason: str
    inspected_at: datetime
    started_on: date
    ended_on: date | None
    inspections: list[MachineInspectionView] = Field(default_factory=list)


class AuditControlCreate(StrictSchema):
    catalog_code: Code
    result: ControlResult
    reason: LongText | None = None
    severity_code: Code | None = None
    finding_description: LongText | None = None

    @model_validator(mode="after")
    def validate_result_details(self) -> Self:
        if self.result in {ControlResult.NO_APLICA, ControlResult.NO_VERIFICADO}:
            if self.reason is None:
                raise ValueError("reason es obligatorio para NO_APLICA y NO_VERIFICADO")
        if self.result is ControlResult.NO_CUMPLE:
            if self.severity_code is None or self.finding_description is None:
                raise ValueError(
                    "severity_code y finding_description son obligatorios para NO_CUMPLE"
                )
        elif self.severity_code is not None or self.finding_description is not None:
            raise ValueError("severity_code y finding_description sólo se permiten para NO_CUMPLE")
        return self


class AuditControlView(StrictSchema):
    id: UUID
    catalog_code: str
    catalog_title: str
    result: ControlResult
    reason: str | None
    finding_id: UUID | None


class AuditCatalogControlView(StrictSchema):
    catalog_code: str
    catalog_title: str


class CorrectionCreate(StrictSchema):
    description: LongText
    evidence_note: LongText


class CorrectionView(StrictSchema):
    id: UUID
    description: str
    evidence_note: str
    created_by: UUID
    created_at: datetime


class VerificationCreate(StrictSchema):
    decision: VerificationDecision
    notes: LongText


class VerificationView(StrictSchema):
    id: UUID
    decision: VerificationDecision
    notes: str
    verified_by: UUID
    created_at: datetime


class FindingEventView(StrictSchema):
    id: UUID
    event_type: str
    from_status: FindingStatus | None
    to_status: FindingStatus
    detail: str | None
    actor_id: UUID
    created_at: datetime


class FindingView(StrictSchema):
    id: UUID
    audit_id: UUID
    audit_control_id: UUID
    title: str
    description: str
    severity_code: str
    status: FindingStatus
    due_at: datetime
    overdue: bool
    closed_at: datetime | None
    created_by: UUID
    corrections: list[CorrectionView] = Field(default_factory=list)
    verifications: list[VerificationView] = Field(default_factory=list)
    events: list[FindingEventView] = Field(default_factory=list)


class DocumentMetrics(StrictSchema):
    total: int
    by_status: dict[DocumentDisplayStatus, int]


class FindingMetrics(StrictSchema):
    total: int
    by_status: dict[FindingStatus, int]
    overdue: int


class MachineMetrics(StrictSchema):
    total: int
    by_status: dict[MachineStatus, int]


class LatestAuditView(StrictSchema):
    id: UUID
    status: AuditStatus
    started_at: datetime
    finalized_at: datetime | None


class ControlExclusions(StrictSchema):
    no_aplica: int
    no_verificado: int


class ControlMetrics(StrictSchema):
    audit_id: UUID | None
    numerator: int
    denominator: int
    ratio: float | None
    excluded: ControlExclusions


class WorksiteMetrics(StrictSchema):
    documents: DocumentMetrics
    findings: FindingMetrics
    machines: MachineMetrics
    latest_audit: LatestAuditView | None
    controls: ControlMetrics
    calculated_at: datetime


class AuditView(StrictSchema):
    id: UUID
    status: AuditStatus
    author_id: UUID
    editor_id: UUID
    started_at: datetime
    finalized_at: datetime | None
    available_controls: list[AuditCatalogControlView] = Field(default_factory=list)
    controls: list[AuditControlView] = Field(default_factory=list)


class AuditControlMutationResponse(StrictSchema):
    control: AuditControlView
    finding: FindingView | None


class WorksiteStageCreate(StrictSchema):
    code: Code
    name: ShortText
    started_on: date
    ended_on: date | None = None
    sector: ShortText | None = None
    notes: LongText | None = None

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if self.ended_on is not None and self.ended_on <= self.started_on:
            raise ValueError("ended_on debe ser posterior a started_on")
        return self


class WorksiteStageView(StrictSchema):
    id: UUID
    worksite_id: UUID
    code: str
    name: str
    started_on: date
    ended_on: date | None
    sector: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class WorksiteDetail(WorksiteSummary):
    stages: list[WorksiteStageView] = Field(default_factory=list)
    contractors: list[ContractorView] = Field(default_factory=list)
    people: list[PersonView] = Field(default_factory=list)
    documents: list[DocumentView] = Field(default_factory=list)
    machines: list[MachineView] = Field(default_factory=list)
    audits: list[AuditView] = Field(default_factory=list)
    findings: list[FindingView] = Field(default_factory=list)
    metrics: WorksiteMetrics


class FindingTimeline(StrictSchema):
    finding_id: UUID
    events: list[FindingEventView]


def derive_document_status(
    review_status: DocumentReviewStatus | str,
    expires_on: date | None,
    *,
    today: date,
) -> DocumentDisplayStatus:
    """Deriva la vista documental sin persistir un segundo estado mutable."""

    review = DocumentReviewStatus(review_status)
    if review is DocumentReviewStatus.PENDIENTE:
        return DocumentDisplayStatus.PENDIENTE
    if review is DocumentReviewStatus.RECHAZADO:
        return DocumentDisplayStatus.RECHAZADO
    if expires_on is None:
        return DocumentDisplayStatus.FALTANTE
    if expires_on < today:
        return DocumentDisplayStatus.VENCIDO
    if expires_on <= today + timedelta(days=30):
        return DocumentDisplayStatus.POR_VENCER
    return DocumentDisplayStatus.VIGENTE


def derive_worksite_metrics(
    documents: Sequence[DocumentView],
    findings: Sequence[FindingView],
    machines: Sequence[MachineView],
    audits: Sequence[AuditView],
    *,
    now: datetime,
) -> WorksiteMetrics:
    """Derive dashboard metrics from the same records exposed in worksite detail."""

    document_by_status = {status: 0 for status in DocumentDisplayStatus}
    for document in documents:
        document_by_status[DocumentDisplayStatus(document.status)] += 1

    finding_by_status = {status: 0 for status in FindingStatus}
    overdue = 0
    for finding in findings:
        finding_by_status[FindingStatus(finding.status)] += 1
        if finding.status is not FindingStatus.CERRADO and finding.due_at < now:
            overdue += 1

    machine_by_status = {status: 0 for status in MachineStatus}
    for machine in machines:
        machine_by_status[MachineStatus(machine.status)] += 1

    latest_audit = max(
        audits,
        key=lambda audit: (audit.started_at, str(audit.id)),
        default=None,
    )
    controls = latest_audit.controls if latest_audit is not None else ()
    numerator = sum(control.result is ControlResult.CUMPLE for control in controls)
    non_compliant = sum(control.result is ControlResult.NO_CUMPLE for control in controls)
    denominator = numerator + non_compliant
    ratio = numerator / denominator if denominator else None

    return WorksiteMetrics(
        documents=DocumentMetrics(
            total=len(documents),
            by_status=document_by_status,
        ),
        findings=FindingMetrics(
            total=len(findings),
            by_status=finding_by_status,
            overdue=overdue,
        ),
        machines=MachineMetrics(
            total=len(machines),
            by_status=machine_by_status,
        ),
        latest_audit=(
            LatestAuditView(
                id=latest_audit.id,
                status=latest_audit.status,
                started_at=latest_audit.started_at,
                finalized_at=latest_audit.finalized_at,
            )
            if latest_audit is not None
            else None
        ),
        controls=ControlMetrics(
            audit_id=latest_audit.id if latest_audit is not None else None,
            numerator=numerator,
            denominator=denominator,
            ratio=ratio,
            excluded=ControlExclusions(
                no_aplica=sum(control.result is ControlResult.NO_APLICA for control in controls),
                no_verificado=sum(
                    control.result is ControlResult.NO_VERIFICADO for control in controls
                ),
            ),
        ),
        calculated_at=now,
    )
