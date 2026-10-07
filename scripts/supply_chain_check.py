"""Check the actual workflow and dependency license metadata with bounded output."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {
    "MIT",
    "ISC",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "BSD-3-Clause-Clear",
    "0BSD",
    "CC0-1.0",
    "CC-BY-4.0",
    "Python-2.0",
    "PSF-2.0",
    "BlueOak-1.0.0",
    "Unlicense",
    "MIT-0",
}
EXISTING_LICENSE_OBLIGATIONS = {
    "LGPL-3.0-or-later": ("node_modules/@img/sharp-",),
    "MPL-2.0": ("node_modules/lightningcss", "node_modules/axe-core"),
}


def check_licenses(lock: dict) -> list[str]:
    failures = []
    for name, package in lock.get("packages", {}).items():
        if not name or package.get("link"):
            continue
        license_value = package.get("license", "")
        ids = re.split(r"\s+(?:OR|AND)\s+", license_value.strip("()"))
        if not ids or any(
            item.strip("() ") not in ALLOWED
            and not name.startswith(
                EXISTING_LICENSE_OBLIGATIONS.get(item.strip("() "), ())
            )
            for item in ids
        ):
            failures.append(
                f"license-review-required package={name} license={license_value or 'unknown'}"
            )
    return failures


def check_workflow(workflow: dict) -> list[str]:
    failures = []
    if workflow.get("permissions") != {"contents": "read"}:
        failures.append("workflow must have read-only default permissions")
    for name, job in workflow.get("jobs", {}).items():
        if not isinstance(job.get("timeout-minutes"), int):
            failures.append(f"job={name} missing timeout")
        if job.get("permissions", {"contents": "read"}) != {"contents": "read"}:
            failures.append(f"job={name} permissions exceed read-only")
        for step in job.get("steps", []):
            if "uses" in step and not re.fullmatch(
                r"[\w./-]+@[a-f0-9]{40}", step["uses"]
            ):
                failures.append(f"job={name} unpinned action")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-inventory", type=Path)
    args = parser.parse_args()
    if args.python_inventory:
        components = []
        for package in importlib.metadata.distributions():
            license_value = (
                package.metadata.get("License-Expression")
                or package.metadata.get("License")
                or "unknown"
            )
            components.append(
                {
                    "type": "library",
                    "name": package.metadata["Name"],
                    "version": package.version,
                    "licenses": [{"license": {"name": license_value}}],
                }
            )
        args.python_inventory.write_text(
            json.dumps(
                {
                    "bomFormat": "CycloneDX",
                    "specVersion": "1.6",
                    "version": 1,
                    "components": components,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(
            f"Python inventory generated: {len(components)} distributions; license review still required."
        )
        return 0
    import yaml  # Isolated, exact-pinned CI tooling; not an application dependency.

    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    )
    failures = check_workflow(workflow) + check_licenses(
        json.loads(
            (ROOT / "apps/web/package-lock.json").read_text(encoding="utf-8-sig")
        )
    )
    if failures:
        print("\n".join(failures))
        return 1
    print("Workflow structure/actions/permissions and npm license allowlist passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
