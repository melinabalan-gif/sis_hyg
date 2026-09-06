"""Rutas del primer recorrido vertical, exclusivamente sintético."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from hys_api.api.dependencies import reject_query_parameters
from hys_api.core.errors import problem_openapi_response
from hys_api.modules.pilot.report import build_audit_report_pdf, build_worksite_report_pdf
from hys_api.modules.pilot.schemas import (
    AuditControlCreate,
    AuditControlMutationResponse,
    AuditStartCreate,
    AuditView,
    ContractorCreate,
    ContractorView,
    CorrectionCreate,
    DocumentCreate,
    DocumentReviewCreate,
    DocumentVersionCreate,
    DocumentView,
    FindingTimeline,
    FindingView,
    MachineCreate,
    MachineInspectionCreate,
    MachineInspectionValidationCreate,
    MachineView,
    PersonCreate,
    PersonVerificationCreate,
    PersonView,
    UnregisteredPersonFindingCreate,
    VerificationCreate,
    WorksiteCreate,
    WorksiteDetail,
    WorksiteFunctionalAssignmentChange,
    WorksiteFunctionalAssignmentCreate,
    WorksiteFunctionalAssignmentFinish,
    WorksiteFunctionalAssignmentView,
    WorksiteStageCreate,
    WorksiteStageUpdate,
    WorksiteStageView,
    WorksiteSummary,
)
from hys_api.modules.pilot.service import PilotService, get_pilot_service

PilotServiceDependency = Annotated[PilotService, Depends(get_pilot_service)]

COMMON_ERRORS: dict[int | str, dict[str, Any]] = {
    401: problem_openapi_response("Actor sintético ausente o inválido"),
    403: problem_openapi_response("El rol del piloto no permite la acción"),
    404: problem_openapi_response("Recurso no visible"),
    409: problem_openapi_response("Estado, duplicado o segregación de funciones"),
    422: problem_openapi_response("Solicitud inválida"),
}

router = APIRouter(
    tags=["pilot"],
    dependencies=[Depends(reject_query_parameters)],
)


@router.get(
    "/worksites",
    operation_id="pilot_list_worksites",
    response_model=list[WorksiteSummary],
    responses=COMMON_ERRORS,
)
async def list_worksites(service: PilotServiceDependency) -> list[WorksiteSummary]:
    return await service.list_worksites()


@router.post(
    "/worksites",
    operation_id="pilot_create_worksite",
    response_model=WorksiteSummary,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
)
async def create_worksite(
    payload: WorksiteCreate,
    service: PilotServiceDependency,
) -> WorksiteSummary:
    return await service.create_worksite(payload)


@router.get(
    "/worksites/{worksite_id}",
    operation_id="pilot_get_worksite",
    response_model=WorksiteDetail,
    responses=COMMON_ERRORS,
)
async def get_worksite(
    worksite_id: UUID,
    service: PilotServiceDependency,
) -> WorksiteDetail:
    return await service.get_worksite_detail(worksite_id)


@router.get(
    "/worksites/{worksite_id}/report.pdf",
    operation_id="pilot_download_worksite_report",
    response_class=Response,
    responses={
        **COMMON_ERRORS,
        200: {
            "description": "Synchronous synthetic worksite report",
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        },
    },
)
async def download_worksite_report(
    worksite_id: UUID,
    service: PilotServiceDependency,
) -> Response:
    detail = await service.get_worksite_detail(worksite_id)
    filename = f"{detail.code.lower()}-reporte.pdf"
    return Response(
        content=build_worksite_report_pdf(detail),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/audits/{audit_id}",
    operation_id="pilot_get_audit",
    response_model=AuditView,
    responses=COMMON_ERRORS,
)
async def get_audit(audit_id: UUID, service: PilotServiceDependency) -> AuditView:
    audit = await service._get_audit(audit_id)
    await service._require_read_access(audit.worksite_id)
    return await service._audit_view(audit)


@router.get(
    "/audits/{audit_id}/report.pdf",
    operation_id="pilot_download_audit_report",
    response_class=Response,
    responses={
        **COMMON_ERRORS,
        200: {
            "description": "Synthetic audit report",
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        },
    },
)
async def download_audit_report(audit_id: UUID, service: PilotServiceDependency) -> Response:
    audit = await service._get_audit(audit_id)
    detail = await service.get_worksite_detail(audit.worksite_id)
    return Response(
        content=build_audit_report_pdf(detail, audit_id),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="auditoria-{str(audit_id)[:8]}.pdf"'
        },
    )


@router.post(
    "/worksites/{worksite_id}/stages",
    operation_id="pilot_create_worksite_stage",
    response_model=WorksiteStageView,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
)
async def create_worksite_stage(
    worksite_id: UUID,
    payload: WorksiteStageCreate,
    service: PilotServiceDependency,
) -> WorksiteStageView:
    return await service.create_worksite_stage(worksite_id, payload)


@router.put(
    "/worksites/{worksite_id}/stages/{stage_id}",
    operation_id="pilot_update_worksite_stage",
    response_model=WorksiteStageView,
    responses=COMMON_ERRORS,
)
async def update_worksite_stage(
    worksite_id: UUID,
    stage_id: UUID,
    payload: WorksiteStageUpdate,
    service: PilotServiceDependency,
) -> WorksiteStageView:
    return await service.update_worksite_stage(worksite_id, stage_id, payload)


@router.post(
    "/worksites/{worksite_id}/contractors",
    operation_id="pilot_create_worksite_contractor",
    response_model=ContractorView,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
)
async def create_worksite_contractor(
    worksite_id: UUID,
    payload: ContractorCreate,
    service: PilotServiceDependency,
) -> ContractorView:
    return await service.create_contractor(worksite_id, payload)


@router.get(
    "/worksites/{worksite_id}/functional-assignments",
    operation_id="pilot_list_worksite_functional_assignments",
    response_model=list[WorksiteFunctionalAssignmentView],
    responses=COMMON_ERRORS,
)
async def list_worksite_functional_assignments(
    worksite_id: UUID,
    service: PilotServiceDependency,
) -> list[WorksiteFunctionalAssignmentView]:
    return await service.list_functional_assignments(worksite_id)


@router.post(
    "/worksites/{worksite_id}/functional-assignments",
    operation_id="pilot_create_worksite_functional_assignment",
    response_model=WorksiteFunctionalAssignmentView,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
)
async def create_worksite_functional_assignment(
    worksite_id: UUID,
    payload: WorksiteFunctionalAssignmentCreate,
    service: PilotServiceDependency,
) -> WorksiteFunctionalAssignmentView:
    return await service.create_functional_assignment(worksite_id, payload)


@router.post(
    "/worksites/{worksite_id}/functional-assignments/{assignment_id}/change",
    operation_id="pilot_change_worksite_functional_assignment",
    response_model=WorksiteFunctionalAssignmentView,
    responses=COMMON_ERRORS,
)
async def change_worksite_functional_assignment(
    worksite_id: UUID,
    assignment_id: UUID,
    payload: WorksiteFunctionalAssignmentChange,
    service: PilotServiceDependency,
) -> WorksiteFunctionalAssignmentView:
    return await service.change_functional_assignment(worksite_id, assignment_id, payload)


@router.post(
    "/worksites/{worksite_id}/functional-assignments/{assignment_id}/finish",
    operation_id="pilot_finish_worksite_functional_assignment",
    response_model=WorksiteFunctionalAssignmentView,
    responses=COMMON_ERRORS,
)
async def finish_worksite_functional_assignment(
    worksite_id: UUID,
    assignment_id: UUID,
    service: PilotServiceDependency,
    payload: WorksiteFunctionalAssignmentFinish | None = None,
) -> WorksiteFunctionalAssignmentView:
    return await service.finish_functional_assignment(
        worksite_id, assignment_id, payload or WorksiteFunctionalAssignmentFinish()
    )


@router.post(
    "/worksites/{worksite_id}/people",
    operation_id="pilot_create_worksite_person",
    response_model=PersonView,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
)
async def create_worksite_person(
    worksite_id: UUID,
    payload: PersonCreate,
    service: PilotServiceDependency,
) -> PersonView:
    return await service.create_person(worksite_id, payload)


@router.post(
    "/worksites/{worksite_id}/people/{person_id}/verifications",
    operation_id="pilot_verify_person_habilitation",
    response_model=PersonView,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
)
async def verify_person_habilitation(
    worksite_id: UUID,
    person_id: UUID,
    payload: PersonVerificationCreate,
    service: PilotServiceDependency,
) -> PersonView:
    return await service.verify_person(worksite_id, person_id, payload)


@router.post(
    "/worksites/{worksite_id}/documents",
    operation_id="pilot_create_worksite_document",
    response_model=DocumentView,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
)
async def create_worksite_document(
    worksite_id: UUID,
    payload: DocumentCreate,
    service: PilotServiceDependency,
) -> DocumentView:
    return await service.create_document(worksite_id, payload)


@router.post(
    "/worksites/{worksite_id}/documents/{document_id}/versions",
    operation_id="pilot_create_worksite_document_version",
    response_model=DocumentView,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
)
async def create_worksite_document_version(
    worksite_id: UUID,
    document_id: UUID,
    payload: DocumentVersionCreate,
    service: PilotServiceDependency,
) -> DocumentView:
    return await service.create_document_version(worksite_id, document_id, payload)


@router.post(
    "/worksites/{worksite_id}/documents/{document_id}/reviews",
    operation_id="pilot_review_worksite_document",
    response_model=DocumentView,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
)
async def review_worksite_document(
    worksite_id: UUID,
    document_id: UUID,
    payload: DocumentReviewCreate,
    service: PilotServiceDependency,
) -> DocumentView:
    return await service.review_document(worksite_id, document_id, payload)


@router.post(
    "/worksites/{worksite_id}/machines",
    operation_id="pilot_create_worksite_machine",
    response_model=MachineView,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
)
async def create_worksite_machine(
    worksite_id: UUID,
    payload: MachineCreate,
    service: PilotServiceDependency,
) -> MachineView:
    return await service.create_machine(worksite_id, payload)


@router.post(
    "/worksites/{worksite_id}/machines/{machine_id}/inspections",
    operation_id="pilot_create_machine_inspection",
    response_model=MachineView,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
)
async def create_machine_inspection(
    worksite_id: UUID,
    machine_id: UUID,
    payload: MachineInspectionCreate,
    service: PilotServiceDependency,
) -> MachineView:
    return await service.create_machine_inspection(worksite_id, machine_id, payload)


@router.post(
    "/worksites/{worksite_id}/machines/{machine_id}/inspections/{inspection_id}/validations",
    operation_id="pilot_validate_machine_inspection",
    response_model=MachineView,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
)
async def validate_machine_inspection(
    worksite_id: UUID,
    machine_id: UUID,
    inspection_id: UUID,
    payload: MachineInspectionValidationCreate,
    service: PilotServiceDependency,
) -> MachineView:
    return await service.validate_machine_inspection(
        worksite_id, machine_id, inspection_id, payload
    )


@router.post(
    "/worksites/{worksite_id}/audits",
    operation_id="pilot_start_worksite_audit",
    response_model=AuditView,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
)
async def start_worksite_audit(
    worksite_id: UUID,
    service: PilotServiceDependency,
    payload: AuditStartCreate | None = None,
) -> AuditView:
    return await service.start_audit(worksite_id, payload)


@router.post(
    "/audits/{audit_id}/controls",
    operation_id="pilot_create_audit_control",
    response_model=AuditControlMutationResponse,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
)
async def create_audit_control(
    audit_id: UUID,
    payload: AuditControlCreate,
    service: PilotServiceDependency,
) -> AuditControlMutationResponse:
    return await service.create_audit_control(audit_id, payload)


@router.post(
    "/audits/{audit_id}/finalize",
    operation_id="pilot_finalize_audit",
    response_model=AuditView,
    responses=COMMON_ERRORS,
)
async def finalize_audit(
    audit_id: UUID,
    service: PilotServiceDependency,
) -> AuditView:
    return await service.finalize_audit(audit_id)


@router.post(
    "/audits/{audit_id}/unregistered-people",
    operation_id="pilot_create_unregistered_person_finding",
    response_model=FindingView,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
)
async def create_unregistered_person_finding(
    audit_id: UUID,
    payload: UnregisteredPersonFindingCreate,
    service: PilotServiceDependency,
) -> FindingView:
    return await service.create_unregistered_person_finding(audit_id, payload)


@router.post(
    "/findings/{finding_id}/corrections",
    operation_id="pilot_create_finding_correction",
    response_model=FindingView,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
)
async def create_finding_correction(
    finding_id: UUID,
    payload: CorrectionCreate,
    service: PilotServiceDependency,
) -> FindingView:
    return await service.create_correction(finding_id, payload)


@router.post(
    "/findings/{finding_id}/submit-verification",
    operation_id="pilot_submit_finding_verification",
    response_model=FindingView,
    responses=COMMON_ERRORS,
)
async def submit_finding_verification(
    finding_id: UUID,
    service: PilotServiceDependency,
) -> FindingView:
    return await service.submit_verification(finding_id)


@router.post(
    "/findings/{finding_id}/verifications",
    operation_id="pilot_verify_finding",
    response_model=FindingView,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
)
async def verify_finding(
    finding_id: UUID,
    payload: VerificationCreate,
    service: PilotServiceDependency,
) -> FindingView:
    return await service.verify_finding(finding_id, payload)


@router.get(
    "/findings/{finding_id}/timeline",
    operation_id="pilot_get_finding_timeline",
    response_model=FindingTimeline,
    responses=COMMON_ERRORS,
)
async def get_finding_timeline(
    finding_id: UUID,
    service: PilotServiceDependency,
) -> FindingTimeline:
    return await service.get_finding_timeline(finding_id)
