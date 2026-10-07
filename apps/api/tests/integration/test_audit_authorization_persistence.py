"""Real tenant-scoped queries and independent verification, not mocked guards."""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from hys_api.api.dependencies import PILOT_ACTORS, PILOT_ORGANIZATION_ID, PilotRequestContext
from hys_api.core.errors import ProblemException
from hys_api.db.tenant import AuthorizationContext, apply_authorization_context
from hys_api.modules.pilot.schemas import (
    AuditControlCreate,
    ContractorCreate,
    CorrectionCreate,
    PersonCreate,
    VerificationCreate,
    WorksiteCreate,
    WorksiteFunctionalAssignmentCreate,
)
from hys_api.modules.pilot.service import PilotService

pytestmark = pytest.mark.integration


async def _run(engine, actor_key, action):
    async with AsyncSession(engine) as session, session.begin():
        await apply_authorization_context(
            session,
            AuthorizationContext(
                organization_id=PILOT_ORGANIZATION_ID, actor_id=PILOT_ACTORS[actor_key].id
            ),
        )
        return await action(PilotService(PilotRequestContext(PILOT_ACTORS[actor_key], session)))


async def _scenario(engine, *, creator="auditor", corrector="tecnico"):
    async def setup(service):
        site = await service.create_worksite(
            WorksiteCreate(
                code=f"SYN-AUTH-{uuid4().hex[:12].upper()}",
                name="Synthetic authorization",
                address="Synthetic address",
                jurisdiction="Synthetic jurisdiction",
            )
        )
        company = await service.create_contractor(
            site.id,
            ContractorCreate(
                legal_name=f"Synthetic principal {site.id}",
                trade="Synthetic",
                started_on=date(2020, 1, 1),
            ),
        )
        project_assignment_id = None
        for actor, function, profession, represented in [
            ("responsable", "RESPONSABLE_HYS_PROYECTO", "LICENCIADO_HYS", None),
            ("tecnico", "TECNICO_HYS_CONTRATISTA_PRINCIPAL", "TECNICO_HYS", company.id),
            (
                "responsable-suplente",
                "RESPONSABLE_HYS_CONTRATISTA_PRINCIPAL",
                "LICENCIADO_HYS",
                company.id,
            ),
            (creator, "AUDITOR", PILOT_ACTORS[creator].profession_code, None),
        ]:
            person = await service.create_person(
                site.id,
                PersonCreate(
                    display_name="Synthetic professional",
                    profession_code=profession,
                    contractor_id=represented,
                    started_on=date(2020, 1, 1),
                ),
            )
            assignment = await service.create_functional_assignment(
                site.id,
                WorksiteFunctionalAssignmentCreate(
                    actor_id=PILOT_ACTORS[actor].id,
                    person_id=person.id,
                    function_code=function,
                    represented_contractor_id=represented,
                    valid_from=date(2020, 1, 1),
                    delegated_by_assignment_id=project_assignment_id
                    if function == "AUDITOR" and profession == "TECNICO_HYS"
                    else None,
                ),
            )
            if function == "RESPONSABLE_HYS_PROYECTO":
                project_assignment_id = assignment.id
        return site, company

    site, company = await _run(engine, "responsable", setup)
    audit = await _run(engine, creator, lambda service: service.start_audit(site.id))
    result = await _run(
        engine,
        creator,
        lambda service: service.create_audit_control(
            audit.id,
            AuditControlCreate(
                catalog_code="SYN-EPP-001",
                result="NO_CUMPLE",
                severity_code="MEDIA",
                finding_description="Synthetic authorization finding",
                affected_contractor_id=company.id,
            ),
        ),
    )
    assert result.finding is not None
    finding = result.finding
    await _run(
        engine,
        corrector,
        lambda service: service.create_correction(
            finding.id,
            CorrectionCreate(
                description="Synthetic correction", evidence_note="Synthetic evidence"
            ),
        ),
    )
    await _run(engine, corrector, lambda service: service.submit_verification(finding.id))
    return site, company, finding


@pytest.mark.parametrize(
    "scope",
    [
        "unassigned",
        "foreign_worksite",
        "expired",
        "foreign_company",
        "creator_only",
        "same_company",
    ],
)
async def test_timeline_real_database_requires_current_worksite_and_company_scope(
    migrated_database,
    app_database_url,
    scope,
):
    engine = create_async_engine(app_database_url)
    owner = create_async_engine(migrated_database)
    try:
        site, company, finding = await _scenario(engine)
        actor = {
            "creator_only": "responsable",
            "unassigned": "licenciado-contratista-principal",
        }.get(scope, "tecnico")
        async with owner.begin() as connection:
            if scope in {"unassigned", "foreign_worksite", "creator_only"}:
                # Close, rather than delete, the assignment while retaining its history.
                await connection.execute(
                    text(
                        "UPDATE worksite_functional_assignments SET valid_to='2021-01-01' "
                        "WHERE worksite_id=:site AND actor_id=:actor"
                    ),
                    {"site": site.id, "actor": PILOT_ACTORS[actor].id},
                )
                if scope == "foreign_worksite":
                    foreign = await _run(
                        engine,
                        "responsable",
                        lambda service: service.create_worksite(
                            WorksiteCreate(
                                name=f"Synthetic foreign {uuid4()}",
                                address="Synthetic",
                                jurisdiction="Synthetic",
                            )
                        ),
                    )
                    await connection.execute(
                        text(
                            "UPDATE worksite_functional_assignments "
                            "SET worksite_id=:foreign, valid_to=NULL "
                            "WHERE worksite_id=:site AND actor_id=:actor"
                        ),
                        {"foreign": foreign.id, "site": site.id, "actor": PILOT_ACTORS[actor].id},
                    )
            elif scope == "expired":
                await connection.execute(
                    text(
                        "UPDATE worksite_functional_assignments SET valid_to='2021-01-01' "
                        "WHERE worksite_id=:site AND actor_id=:actor"
                    ),
                    {"site": site.id, "actor": PILOT_ACTORS[actor].id},
                )
            elif scope == "foreign_company":
                other = await _run(
                    engine,
                    "responsable",
                    lambda service: service.create_contractor(
                        site.id,
                        ContractorCreate(
                            legal_name=f"Synthetic other {site.id}",
                            trade="Synthetic",
                            participation_type="CONTRACTOR",
                            parent_contracting_company_id=company.id,
                        ),
                    ),
                )
                await connection.execute(
                    text(
                        "UPDATE findings SET affected_contractor_id=:other, "
                        "responsible_contractor_id=:other WHERE id=:id"
                    ),
                    {"other": other.id, "id": finding.id},
                )

        def action(service):
            return service.get_finding_timeline(finding.id)

        if scope == "same_company":
            timeline = await _run(engine, actor, action)
            assert timeline.finding_id == finding.id
            assert len(timeline.events) >= 3
        else:
            with pytest.raises(ProblemException) as error:
                await _run(engine, actor, action)
            assert error.value.status == 404
    finally:
        await owner.dispose()
        await engine.dispose()


@pytest.mark.parametrize("relation", ["creator", "corrector", "non_rhs", "same_company_rhs"])
async def test_verification_real_database_requires_independent_rhs(
    migrated_database,
    app_database_url,
    relation,
):
    del migrated_database
    engine = create_async_engine(app_database_url)
    try:
        creator = "responsable" if relation == "creator" else "auditor"
        corrector = "responsable-suplente" if relation == "corrector" else "tecnico"
        site, _, finding = await _scenario(engine, creator=creator, corrector=corrector)
        actor = {
            "creator": "responsable",
            "corrector": "responsable-suplente",
            "non_rhs": "auditor",
            "same_company_rhs": "responsable-suplente",
        }[relation]

        def action(service):
            return service.verify_finding(
                finding.id,
                VerificationCreate(decision="ACEPTADA", notes="Synthetic independent verification"),
            )

        if relation == "same_company_rhs":
            result = await _run(engine, actor, action)
            assert result.status == "CERRADO"
            assert result.verifications[0].verified_by == PILOT_ACTORS[actor].id
        else:
            with pytest.raises(ProblemException) as error:
                await _run(engine, actor, action)
            assert error.value.status == (403 if relation == "non_rhs" else 409)
            result = await _run(
                engine,
                "responsable",
                lambda service: service.get_worksite_detail(site.id),
            )
            stored = next(item for item in result.findings if item.id == finding.id)
            assert stored.status == "PENDIENTE_VERIFICACION"
            assert stored.verifications == []
    finally:
        await engine.dispose()
