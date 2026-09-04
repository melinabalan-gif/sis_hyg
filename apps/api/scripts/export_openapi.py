"""Genera o verifica el contrato OpenAPI versionado."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

API_ROOT = Path(__file__).resolve().parents[1]
TARGET = API_ROOT / "openapi.json"
SYNTHETIC_DATABASE_URL = (
    "postgresql+asyncpg://synthetic_openapi:synthetic_only@127.0.0.1:5432/hys_synthetic"
)


def build_schema() -> dict[str, Any]:
    """Construye OpenAPI sin abrir conexiones ni depender de credenciales reales."""
    os.environ.setdefault("HYS_DATABASE_URL", SYNTHETIC_DATABASE_URL)
    os.environ.setdefault("HYS_ENVIRONMENT", "test")

    from hys_api.core.config import Settings
    from hys_api.main import create_app

    settings = Settings(database_url=SYNTHETIC_DATABASE_URL, environment="test")
    return create_app(settings).openapi()


def render_schema() -> str:
    return json.dumps(build_schema(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="falla si openapi.json no coincide con el contrato actual",
    )
    args = parser.parse_args()
    rendered = render_schema()

    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != rendered:
            print(
                "openapi.json está desactualizado; ejecutá scripts/export_openapi.py",
                file=sys.stderr,
            )
            return 1
        print("OpenAPI snapshot OK")
        return 0

    TARGET.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"OpenAPI actualizado: {TARGET.relative_to(API_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
