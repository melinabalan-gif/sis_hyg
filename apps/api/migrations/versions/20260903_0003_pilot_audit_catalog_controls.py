"""Add representative controls to the synthetic pilot catalog.

Revision ID: 20260903_0003
Revises: 20260903_0002
Create Date: 2026-09-03 00:30:00

The migration is additive and does not update historical audit data. Its
rollback removes only the rows inserted by this revision.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260903_0003"
down_revision: str | None = "20260903_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_SETTING = "00000000-0000-4000-8000-000000000001"
_PUBLISHED_AT = "2026-09-03T00:00:00+00:00"
_CONTROL_IDS = (
    "00000000-0000-4000-8000-000000000102",
    "00000000-0000-4000-8000-000000000103",
)


def upgrade() -> None:
    op.execute(
        sa.text(
            "SELECT set_config('app.current_organization_id', :organization_id, true)"
        ).bindparams(organization_id=_TENANT_SETTING)
    )
    op.execute(
        sa.text(
            """
            INSERT INTO control_catalog_versions
                (id, organization_id, code, title, version_number, published_at)
            VALUES
                (CAST(:circulation_id AS uuid), CAST(:organization_id AS uuid),
                 'SYN-CIRCULACION-001',
                 'Circulación y señalización interna — control sintético',
                 1, CAST(:published_at AS timestamptz)),
                (CAST(:ppe_id AS uuid), CAST(:organization_id AS uuid),
                 'SYN-EPP-001',
                 'Elementos de protección personal — control sintético',
                 1, CAST(:published_at AS timestamptz))
            """
        ).bindparams(
            circulation_id=_CONTROL_IDS[0],
            ppe_id=_CONTROL_IDS[1],
            organization_id=_TENANT_SETTING,
            published_at=_PUBLISHED_AT,
        )
    )
    op.execute("SELECT set_config('app.current_organization_id', '', true)")


def downgrade() -> None:
    op.execute(
        sa.text(
            "SELECT set_config('app.current_organization_id', :organization_id, true)"
        ).bindparams(organization_id=_TENANT_SETTING)
    )
    op.execute(
        sa.text(
            """
            DELETE FROM control_catalog_versions
            WHERE organization_id = CAST(:organization_id AS uuid)
              AND id IN (CAST(:circulation_id AS uuid), CAST(:ppe_id AS uuid))
              AND NOT EXISTS (
                  SELECT 1
                  FROM audits
                  WHERE audits.organization_id = control_catalog_versions.organization_id
                    AND audits.control_catalog_version_id = control_catalog_versions.id
              )
            """
        ).bindparams(
            circulation_id=_CONTROL_IDS[0],
            ppe_id=_CONTROL_IDS[1],
            organization_id=_TENANT_SETTING,
        )
    )
    op.execute("SELECT set_config('app.current_organization_id', '', true)")
