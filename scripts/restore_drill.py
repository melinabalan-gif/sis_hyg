"""Logical PostgreSQL restore drill, restricted to explicit synthetic loopback databases."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit


def connection(url: str, *, target: bool) -> dict[str, str]:
    parts = urlsplit(url.replace("postgresql+asyncpg:", "postgresql:"))
    name = parts.path.lstrip("/")
    if parts.scheme != "postgresql" or parts.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise ValueError(
            "Restore drill requires explicit PostgreSQL loopback URLs; values withheld."
        )
    if (
        not name.endswith("_restore_test" if target else "_test")
        or parts.query
        or parts.fragment
    ):
        raise ValueError(
            "Source must end _test; empty target must end _restore_test; no URL options."
        )
    return {
        "host": parts.hostname,
        "port": str(parts.port or 5432),
        "dbname": name,
        "user": unquote(parts.username or ""),
        "password": unquote(parts.password or ""),
    }


def run(
    executable: str,
    config: dict[str, str],
    *arguments: str,
    container: str = "",
    input_data: bytes | None = None,
) -> bytes:
    env = os.environ.copy()
    env.update(
        PGHOST=config["host"],
        PGPORT=config["port"],
        PGDATABASE=config["dbname"],
        PGUSER=config["user"],
        PGPASSWORD=config["password"],
        PGCONNECT_TIMEOUT="5",
    )
    command = [executable, *arguments]
    if container:
        command = [
            "docker",
            "exec",
            "-i",
            "--env",
            "PGHOST",
            "--env",
            "PGPORT",
            "--env",
            "PGDATABASE",
            "--env",
            "PGUSER",
            "--env",
            "PGPASSWORD",
            "--env",
            "PGCONNECT_TIMEOUT",
            container,
            *command,
        ]
    result = subprocess.run(
        command, env=env, input=input_data, capture_output=True, check=False, timeout=60
    )
    if result.returncode:
        raise RuntimeError(
            f"{Path(executable).name} failed; database values and output withheld."
        )
    return result.stdout


def fingerprint(data: bytes) -> str:
    lines = [
        line
        for line in data.splitlines()
        if line.strip() and not line.startswith((b"--", b"\\restrict", b"\\unrestrict"))
    ]
    return hashlib.sha256(b"\n".join(lines)).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-synthetic-restore", action="store_true")
    parser.add_argument("--pg-bin", type=Path, default=Path("."))
    parser.add_argument(
        "--container",
        default="",
        help="Explicit isolated PostgreSQL container; use version-matched tools",
    )
    args = parser.parse_args()
    try:
        if not args.allow_synthetic_restore or os.getenv("HYS_ENVIRONMENT") != "test":
            raise ValueError(
                "Set HYS_ENVIRONMENT=test and pass --allow-synthetic-restore for an isolated drill."
            )
        source = connection(os.environ.get("HYS_DRILL_SOURCE_URL", ""), target=False)
        target = connection(os.environ.get("HYS_DRILL_TARGET_URL", ""), target=True)
        if (source["host"], source["port"], source["dbname"]) == (
            target["host"],
            target["port"],
            target["dbname"],
        ):
            raise ValueError("Source and target must differ.")

        def executable(name: str) -> str:
            if args.container:
                return name
            path = args.pg_bin / (name + (".exe" if os.name == "nt" else ""))
            return str(path) if path.exists() else name

        count = run(
            executable("psql"),
            target,
            "-X",
            "-Atc",
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'",
            container=args.container,
        )
        if count.strip() != b"0":
            raise ValueError(
                "Target must be empty; drill never cleans or overwrites existing tables."
            )
        dump = run(
            executable("pg_dump"),
            source,
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            container=args.container,
        )
        if len(dump) > 16 * 1024 * 1024:
            raise ValueError(
                "Synthetic drill archive exceeds its bounded 16 MiB scope."
            )
        run(
            executable("pg_restore"),
            target,
            "--dbname",
            target["dbname"],
            "--exit-on-error",
            "--no-owner",
            "--no-privileges",
            container=args.container,
            input_data=dump,
        )
        del dump
        arguments = (
            "--data-only",
            "--no-owner",
            "--no-privileges",
            "--inserts",
            "--rows-per-insert=1",
        )
        before = fingerprint(
            run(executable("pg_dump"), source, *arguments, container=args.container)
        )
        after = fingerprint(
            run(executable("pg_dump"), target, *arguments, container=args.container)
        )
        if before != after:
            raise RuntimeError("Restore data fingerprint mismatch; contents withheld.")
        print(
            "Synthetic logical restore verified; no archive retained. Not a production backup guarantee."
        )
        return 0
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired):
        print(
            "Restore drill rejected/failed; check explicit test URLs, empty target and PostgreSQL tools. Values withheld."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
