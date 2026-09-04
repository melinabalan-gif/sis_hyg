"""Importador explícito de modelos para Alembic."""

from hys_api.modules.organizations.models import Organization
from hys_api.modules.worksites.models import Worksite

__all__ = ["Organization", "Worksite"]
