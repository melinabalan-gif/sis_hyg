"""Fail CI on private source artifacts, likely secrets, or non-synthetic fixtures."""

from __future__ import annotations

import base64
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".css", ".html", ".ini", ".js", ".json", ".md", ".mjs", ".py",
    ".sh", ".toml", ".ts", ".tsx", ".txt", ".yaml", ".yml",
}
SKIP_PARTS = {".git", ".next", ".tools", ".venv", "node_modules"}
SECRET_PATTERN = re.compile(
    r"(?i)(?:password|secret|api[_-]?key|access[_-]?key)\s*[:=]\s*"
    r"(?:['\"])?(?!CHANGE_ME|\$\{|<)[A-Za-z0-9+/_.-]{12,}"
)


def iter_source_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix.lower() in TEXT_SUFFIXES
        and not any(part in SKIP_PARTS for part in path.parts)
        and path.name != ".env.example"
    ]


def protected_terms() -> list[str]:
    encoded = os.getenv("HYS_RESTRICTED_TERMS_B64", "")
    if not encoded:
        return []
    try:
        return [
            term.strip().casefold()
            for term in base64.b64decode(encoded).decode("utf-8").splitlines()
            if term.strip()
        ]
    except (ValueError, UnicodeDecodeError) as exc:
        raise SystemExit(f"HYS_RESTRICTED_TERMS_B64 inválido: {exc}") from exc


def main() -> int:
    failures: list[str] = []
    terms = protected_terms()
    for path in iter_source_files():
        content = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT)
        if SECRET_PATTERN.search(content):
            failures.append(f"{relative}: posible secreto literal")
        folded = content.casefold()
        if any(term in folded for term in terms):
            failures.append(f"{relative}: término restringido protegido")

    forbidden_artifacts = [
        path.relative_to(ROOT)
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in SKIP_PARTS for part in path.parts)
        and path.suffix.lower() in {".doc", ".docx", ".xls", ".xlsx"}
    ]
    failures.extend(f"{path}: fuente binaria no permitida" for path in forbidden_artifacts)

    if failures:
        print("Policy check rechazado:", file=sys.stderr)
        print("\n".join(f"- {failure}" for failure in failures), file=sys.stderr)
        return 1
    print("Policy check OK: sin secretos literales ni fuentes restringidas detectadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

