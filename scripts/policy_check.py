"""Heuristic secret/PII/restricted-artifact scan; never print detected values."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".ps1",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
PRIVATE_SUFFIXES = {".doc", ".docx", ".xls", ".xlsx", ".pem", ".key", ".p12", ".pfx"}
MAX_BYTES = 5 * 1024 * 1024
TOKEN = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,}|"
    r"AKIA[A-Z0-9]{16}|sk-[A-Za-z0-9_-]{24,})\b|"
    r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"
)
ASSIGNMENT = re.compile(
    r"(?i)\b(?:password|secret|token|api[_-]?key|access[_-]?key)"
    r"['\"]?\s*[:=]\s*['\"]([A-Za-z0-9+/_.-]{12,})['\"]"
)
YAML_CREDENTIAL = re.compile(
    r"(?mi)^\s*(?:password|secret|token|api[_-]?key|access[_-]?key)"
    r"\s*:\s*([A-Za-z0-9+/_.-]{12,})\s*$"
)
URI_CREDENTIAL = re.compile(
    r"(?i)\b(?:postgres(?:ql)?(?:\+\w+)?|https?)://[^\s/:]+:([^\s/@]+)@"
)
PII = re.compile(r"(?i)\b(?:dni|cuil|cuit)\b\s*[:=]\s*['\"]?(\d[\d.-]{6,14})")
EMAIL = re.compile(
    r"(?i)\b(?:email|e-mail)\s*[:=]\s*['\"]?([A-Z0-9._%+-]+@([A-Z0-9.-]+))"
)


def synthetic(value: str) -> bool:
    return value == "not-a-secret" or value.upper().startswith(
        ("CHANGE_ME", "SYNTHETIC", "TEST_", "EXAMPLE", "${", "<")
    )


def protected_terms() -> list[str]:
    encoded = os.getenv("HYS_RESTRICTED_TERMS_B64", "")
    if not encoded:
        return []
    try:
        return [
            term.strip().casefold()
            for term in base64.b64decode(encoded, validate=True)
            .decode("utf-8")
            .splitlines()
            if term.strip()
        ]
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise SystemExit(
            "Restricted-term configuration is invalid; value withheld."
        ) from exc


def detect(content: str, terms: list[str]) -> list[str]:
    reasons = []
    if (
        TOKEN.search(content)
        or any(not synthetic(match[1]) for match in ASSIGNMENT.finditer(content))
        or any(not synthetic(match[1]) for match in YAML_CREDENTIAL.finditer(content))
        or any(not synthetic(match[1]) for match in URI_CREDENTIAL.finditer(content))
    ):
        reasons.append("secret")
    if any(
        set(re.sub(r"\D", "", match[1])) != {"0"} for match in PII.finditer(content)
    ) or any(
        not match[2].lower().endswith((".invalid", ".example", "localhost"))
        for match in EMAIL.finditer(content)
    ):
        reasons.append("pii")
    if any(term in content.casefold() for term in terms):
        reasons.append("restricted")
    return reasons


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False
    )
    if result.returncode:
        raise RuntimeError("Git inspection failed; diagnostics withheld.")
    return result.stdout


def inspect_content(
    identity: str, name: str, data: bytes, terms: list[str]
) -> list[str]:
    opaque = hashlib.sha256(identity.encode()).hexdigest()[:12]
    label = f"{identity.split(':', 1)[0]} artifact={opaque}"
    suffix = Path(name).suffix.lower()
    if suffix in PRIVATE_SUFFIXES or Path(name).name == ".env":
        return [f"{label} forbidden-artifact"]
    if suffix not in TEXT_SUFFIXES and Path(name).name not in {
        "Caddyfile",
        ".npmrc",
        ".env.example",
    }:
        return []
    if len(data) > MAX_BYTES:
        return [f"{label} scan-size-limit"]
    try:
        content = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [f"{label} invalid-utf8"]
    return [f"{label} {reason}" for reason in detect(content, terms)]


def scan_repository(root: Path, terms: list[str], *, history: bool) -> list[str]:
    failures = []
    names = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    tracked = set(git(root, "ls-files", "-z").decode().split("\0"))
    for name in dict.fromkeys(names.decode().split("\0")):
        if not name:
            continue
        path = root / name
        if name not in tracked and (".atl" in path.parts or ".backup" in path.name):
            continue
        if path.is_file():
            failures.extend(
                inspect_content(f"worktree:{name}", name, path.read_bytes(), terms)
            )
    if history:
        if git(root, "rev-parse", "--is-shallow-repository").strip() == b"true":
            return failures + ["history incomplete-shallow-clone"]
        for row in git(root, "rev-list", "--objects", "--all").decode().splitlines():
            object_id, _, name = row.partition(" ")
            if not name or git(root, "cat-file", "-t", object_id).strip() != b"blob":
                continue
            if int(git(root, "cat-file", "-s", object_id)) > MAX_BYTES:
                failures.append("history scan-size-limit")
                continue
            failures.extend(
                inspect_content(
                    f"history:{object_id}",
                    name,
                    git(root, "cat-file", "blob", object_id),
                    terms,
                )
            )
    return sorted(set(failures))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--require-restricted-terms", action="store_true")
    args = parser.parse_args()
    terms = protected_terms()
    if args.require_restricted_terms and not terms:
        print(
            "Restricted-term configuration missing; protected corpus scan not performed.",
            file=sys.stderr,
        )
        return 1
    try:
        failures = scan_repository(ROOT, terms, history=args.history)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if failures:
        print("Policy rejected (values and paths withheld):", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(
        "Policy heuristics passed; this is not proof that all PII/secrets are absent."
    )
    if not terms:
        print("Restricted corpus not configured; production privacy gate remains open.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
