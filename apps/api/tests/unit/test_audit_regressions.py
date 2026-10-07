from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint
from sqlalchemy.ext.asyncio import AsyncSession

from hys_api.api.dependencies import PILOT_ACTORS, PILOT_ORGANIZATION_ID, PilotRequestContext
from hys_api.core.errors import ProblemException
from hys_api.modules.pilot.models import (
    Correction,
    Document,
    DocumentReview,
    DocumentVersion,
    Finding,
    WorksiteFunctionalAssignment,
)
from hys_api.modules.pilot.schemas import (
    ContractorCreate,
    DocumentCreate,
    DocumentReviewCreate,
    DocumentVersionCreate,
    MachineCreate,
    PersonCreate,
    PersonVerificationCreate,
    SubjectKind,
    VerificationCreate,
    WorksiteCreate,
    WorksiteStageCreate,
    WorksiteStageUpdate,
)
from hys_api.modules.pilot.service import PilotService
from hys_api.modules.worksites.models import Worksite


def test_document_review_metadata_requires_version_without_rewriting_legacy():
    checks = {
        str(constraint.name): constraint
        for constraint in DocumentReview.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    constraint = checks["ck_document_reviews_version_required"]
    assert str(constraint.sqltext) == "document_version_id IS NOT NULL"
    assert constraint.dialect_options["postgresql"]["not_valid"] is True
    assert DocumentReview.__table__.c.document_version_id.nullable is True


def make_service(actor_key="tecnico"):
    session = MagicMock(spec=AsyncSession)
    session.scalar = AsyncMock()
    session.scalars = AsyncMock(return_value=[])
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    service = PilotService(PilotRequestContext(actor=PILOT_ACTORS[actor_key], session=session))
    return service, session


@pytest.mark.parametrize("assignment_state", ["unassigned", "expired"])
async def test_timeline_denies_worksite_without_current_assignment(assignment_state):
    service, session = make_service()
    finding = Finding(id=uuid4(), worksite_id=uuid4(), organization_id=PILOT_ORGANIZATION_ID)
    # The scoped worksite query returns no row for absent or expired assignments.
    session.scalar.side_effect = [finding, None]
    with pytest.raises(ProblemException) as error:
        await service.get_finding_timeline(finding.id)
    assert error.value.status == 404
    session.scalars.assert_not_awaited()
    query = str(session.scalar.await_args_list[1].args[0])
    assert "valid_from" in query and "valid_to" in query
    assert "actor_id" in query and "permission_scope" in query


async def test_timeline_denies_finding_outside_represented_company():
    service, session = make_service()
    wid = uuid4()
    own_company, foreign_company = uuid4(), uuid4()
    finding = Finding(
        id=uuid4(),
        worksite_id=wid,
        organization_id=PILOT_ORGANIZATION_ID,
        affected_contractor_id=foreign_company,
    )
    worksite = Worksite(id=wid, created_by_actor_id=PILOT_ACTORS["responsable"].id)
    assignment = WorksiteFunctionalAssignment(
        actor_id=service.context.actor.id,
        function_code="TECNICO_HYS_CONTRATISTA_PRINCIPAL",
        permission_scope="WORKSITE",
        represented_contractor_id=own_company,
        valid_from=date(2020, 1, 1),
    )
    session.scalar.side_effect = [finding, worksite, assignment]
    session.scalars.return_value = [assignment]
    service._events_for_finding = AsyncMock(return_value=[])
    with pytest.raises(ProblemException) as error:
        await service.get_finding_timeline(finding.id)
    assert error.value.status == 404
    service._events_for_finding.assert_not_awaited()


async def test_timeline_reads_same_company_after_scope_checks():
    service, session = make_service()
    wid, company = uuid4(), uuid4()
    finding = Finding(
        id=uuid4(),
        worksite_id=wid,
        organization_id=PILOT_ORGANIZATION_ID,
        affected_contractor_id=company,
    )
    worksite = Worksite(id=wid, created_by_actor_id=PILOT_ACTORS["responsable"].id)
    assignment = WorksiteFunctionalAssignment(
        actor_id=service.context.actor.id,
        function_code="TECNICO_HYS_CONTRATISTA_PRINCIPAL",
        permission_scope="WORKSITE",
        represented_contractor_id=company,
        valid_from=date(2020, 1, 1),
    )
    session.scalar.side_effect = [finding, worksite, assignment]
    session.scalars.return_value = [assignment]
    service._events_for_finding = AsyncMock(return_value=[])
    result = await service.get_finding_timeline(finding.id)
    assert result.finding_id == finding.id
    service._events_for_finding.assert_awaited_once_with(finding.id)


@pytest.mark.parametrize("relation", ["current_author", "stale", "independent"])
async def test_document_review_is_bound_to_current_immutable_version(relation):
    service, session = make_service("responsable")
    wid, did, vid = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    document = Document(
        id=did,
        organization_id=PILOT_ORGANIZATION_ID,
        title="Synthetic document",
        document_type="SYN",
        version=2,
        review_status="PENDIENTE",
        created_at=now,
        uploaded_by_actor_id=PILOT_ACTORS["tecnico"].id,
        uploaded_at=now,
    )
    current = DocumentVersion(
        id=vid,
        organization_id=PILOT_ORGANIZATION_ID,
        document_id=did,
        version_number=2,
        actor_id=service.context.actor.id
        if relation == "current_author"
        else PILOT_ACTORS["tecnico"].id,
    )
    session.scalar.side_effect = [document, current]

    async def refresh(row):
        if isinstance(row, DocumentReview):
            row.id = uuid4()
            row.reviewed_at = now

    session.refresh.side_effect = refresh
    service._get_active_worksite = AsyncMock()
    service._document_subject_for_worksite = AsyncMock(
        return_value=(SubjectKind.WORKSITE, wid, "Synthetic")
    )
    service._subject_contractor_id = AsyncMock(return_value=None)
    service._require_current_function = AsyncMock(
        return_value=SimpleNamespace(function_code="RESPONSABLE_HYS_PROYECTO")
    )
    service._document_versions_for_documents = AsyncMock(return_value={})
    service._document_reviews_for_documents = AsyncMock(return_value={})
    payload = DocumentReviewCreate(
        document_version_id=uuid4() if relation == "stale" else vid,
        result="APROBADO",
        foundation="Synthetic independent review",
    )
    if relation == "independent":
        await service.review_document(wid, did, payload)
        review = session.add.call_args.args[0]
        assert review.document_version_id == vid
    else:
        with pytest.raises(ProblemException) as error:
            await service.review_document(wid, did, payload)
        assert error.value.code == (
            "document_reviewer_must_be_independent"
            if relation == "current_author"
            else "document_version_stale"
        )
        session.add.assert_not_called()


def test_worksite_jurisdiction_is_required_with_address():
    with pytest.raises(ValidationError, match="jurisdiction"):
        WorksiteCreate(name="Synthetic worksite", address="Synthetic address")


def test_worksite_address_survives_summary_projection():
    now = datetime.now(UTC)
    row = Worksite(
        id=uuid4(),
        code="SYN-001",
        name="Synthetic",
        address="Synthetic address",
        jurisdiction="Synthetic jurisdiction",
        status="ACTIVE",
        version=1,
        created_at=now,
        updated_at=now,
    )
    summary = PilotService._worksite_summary(row)
    assert summary.address == row.address


@pytest.mark.parametrize(
    "fields",
    [
        {"jurisdiction": "Synthetic"},
        {"country": "Synthetic", "province": "Synthetic", "municipality": "Synthetic"},
    ],
)
def test_worksite_accepts_canonical_jurisdiction_forms(fields):
    payload = WorksiteCreate(name="Synthetic", address="Synthetic", **fields)
    assert payload.address == "Synthetic"


@pytest.mark.parametrize(
    ("actor_key", "relation", "expected"),
    [
        ("auditor", "independent", 403),
        ("responsable", "creator", 409),
        ("responsable", "corrector", 409),
        ("responsable", "independent", None),
        ("responsable-suplente", "independent", None),
    ],
)
async def test_finding_verification_requires_independent_rhs(actor_key, relation, expected):
    service, session = make_service(actor_key)
    finding = Finding(
        id=uuid4(),
        worksite_id=uuid4(),
        status="PENDIENTE_VERIFICACION",
        version=1,
        created_by_actor_id=service.context.actor.id if relation == "creator" else uuid4(),
    )
    correction = Correction(
        authored_by_actor_id=service.context.actor.id if relation == "corrector" else uuid4()
    )
    service._get_finding = AsyncMock(return_value=finding)
    service._latest_correction = AsyncMock(return_value=correction)
    service._require_current_function = AsyncMock()
    service._authorize_finding_scope = AsyncMock()
    service._finding_view = AsyncMock(return_value=SimpleNamespace(status="CERRADO"))
    payload = VerificationCreate(decision="ACEPTADA", notes="Synthetic independent verification")
    if expected is not None:
        with pytest.raises(ProblemException) as error:
            await service.verify_finding(finding.id, payload)
        assert error.value.status == expected
        session.add_all.assert_not_called()
    else:
        result = await service.verify_finding(finding.id, payload)
        assert result.status == "CERRADO"
        assert finding.status == "CERRADO"


@pytest.mark.parametrize(
    ("schema", "base", "field", "limit"),
    [
        *[
            (
                WorksiteCreate,
                {"name": "Synthetic", "address": "Synthetic", "jurisdiction": "Synthetic"},
                field,
                120,
            )
            for field in ["country", "province", "municipality"]
        ],
        (ContractorCreate, {"legal_name": "Synthetic", "trade": "Synthetic"}, "trade", 120),
        (PersonCreate, {"display_name": "Synthetic"}, "role_label", 120),
        (
            WorksiteStageCreate,
            {"code": "SYN", "name": "Synthetic", "started_on": date(2020, 1, 1)},
            "sector",
            120,
        ),
        (WorksiteStageUpdate, {}, "sector", 120),
        (
            PersonVerificationCreate,
            {"status": "HABILITADO", "function_label": "Synthetic"},
            "function_label",
            160,
        ),
        (
            DocumentCreate,
            {
                "subject_kind": "WORKSITE",
                "subject_id": uuid4(),
                "title": "Synthetic",
                "document_type": "SYN",
            },
            "document_type",
            100,
        ),
        (
            DocumentVersionCreate,
            {"title": "Synthetic", "document_type": "SYN"},
            "document_type",
            100,
        ),
        *[
            (MachineCreate, {"internal_code": "SYN", "description": "Synthetic"}, field, 120)
            for field in ["machine_type", "brand", "model"]
        ],
        (MachineCreate, {"internal_code": "SYN", "description": "Synthetic"}, "license_plate", 32),
    ],
)
def test_input_lengths_match_persistence_boundaries(schema, base, field, limit):
    valid = schema.model_validate({**base, field: "X" * limit})
    assert getattr(valid, field) == "X" * limit
    with pytest.raises(ValidationError) as error:
        schema.model_validate({**base, field: "X" * (limit + 1)})
    assert error.value.errors()[0]["loc"] == (field,)


async def test_timeline_creation_ownership_does_not_replace_current_function():
    service, session = make_service("responsable")
    wid = uuid4()
    finding = Finding(id=uuid4(), worksite_id=wid, organization_id=PILOT_ORGANIZATION_ID)
    worksite = Worksite(id=wid, created_by_actor_id=service.context.actor.id)
    session.scalar.side_effect = [finding, worksite, None]
    service._events_for_finding = AsyncMock(return_value=[])
    with pytest.raises(ProblemException) as error:
        await service.get_finding_timeline(finding.id)
    assert error.value.status == 404
    service._events_for_finding.assert_not_awaited()


def test_worksite_summary_exposes_setup_owner_for_effective_permissions():
    from hys_api.modules.pilot.schemas import WorksiteSummary

    assert "created_by_actor_id" in WorksiteSummary.model_fields


@pytest.mark.parametrize("hours", [0, 169, True, "12"])
def test_technical_metadata_rejects_invalid_weekly_hours(hours):
    import json

    from pydantic import ValidationError

    from hys_api.modules.pilot.schemas import DocumentVersionCreate

    with pytest.raises(ValidationError):
        DocumentVersionCreate(
            title="Programa",
            document_type="LEGAJO_TECNICO",
            notes=json.dumps(
                {
                    "schema": "hys.technical_metadata.v1",
                    "detail": "Referencia sintética",
                    "weekly_hours": hours,
                }
            ),
        )


async def test_technical_metadata_cannot_reference_foreign_or_inactive_auditor_assignment():
    import json

    service, _ = make_service("responsable")
    service._active_functional_assignments = AsyncMock(return_value=[])
    with pytest.raises(ProblemException) as error:
        await service._validate_technical_metadata_assignment(
            uuid4(),
            json.dumps(
                {"schema": "hys.technical_metadata.v1", "auditor_assignment_id": str(uuid4())}
            ),
        )
    assert error.value.code == "technical_metadata_assignment_invalid"


async def test_project_responsible_can_reference_another_current_auditor():
    import json

    service, session = make_service("responsable")
    assignment_id = uuid4()

    async def matching_assignment(statement):
        parameters = statement.compile().params
        # An AUDITOR assignment belongs to the auditor, not the program editor.
        if service.context.actor.id in parameters.values():
            return []
        return [SimpleNamespace(id=assignment_id)]

    session.scalars.side_effect = matching_assignment
    await service._validate_technical_metadata_assignment(
        uuid4(),
        json.dumps(
            {"schema": "hys.technical_metadata.v1", "auditor_assignment_id": str(assignment_id)}
        ),
    )
    statement = session.scalars.call_args.args[0]
    query = str(statement)
    assert "organization_id" in query
    assert "worksite_id" in query
    assert "function_code" in query
    assert "valid_from" in query and "valid_to" in query
