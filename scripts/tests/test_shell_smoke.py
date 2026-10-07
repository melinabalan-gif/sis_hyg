"""Exercise the POSIX smoke with isolated command doubles, never a live stack."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ShellSmokeTests(unittest.TestCase):
    def test_private_port_and_missing_service_fail_closed(self):
        shell = shutil.which("sh")
        if shell is None:
            candidate = ROOT / ".tools/git/usr/bin/sh.exe"
            shell = str(candidate) if candidate.exists() else None
        self.assertIsNotNone(shell, "POSIX shell required for parity regression")
        with tempfile.TemporaryDirectory(prefix="hys-smoke-mock-") as directory:
            root = Path(directory)
            (root / "curl").write_text(
                '#!/bin/sh\nfor arg; do url="$arg"; done\ncase "$url" in\n'
                ' */live) printf \'{"status":"ok"}\';;\n'
                ' */ready) printf \'{"status":"ready"}\';;\n'
                " *) printf 'DATOS 100 %% SINTÉTICOS';;\nesac\n",
                encoding="utf-8",
            )
            (root / "docker").write_text(
                '#!/bin/sh\ncase "$*" in\n'
                ' "compose ps --status exited --services migrate") echo migrate;;\n'
                ' "compose ps -a --format json migrate") echo \'{"ExitCode":0}\';;\n'
                ' "compose ps -q "*) if [ "$HYS_MOCK_MISSING" != 1 ]; then echo synthetic; fi;;\n'
                ' "port "*) exit 1;;\n'
                ' "inspect "*) if [ "$HYS_MOCK_PUBLISHED" = 1 ]; then echo \'[{"HostPort":"12345"}]\'; else echo null; fi;;\n'
                " *) exit 2;;\nesac\n",
                encoding="utf-8",
            )
            for command in ("curl", "docker"):
                (root / command).chmod(0o700)
            # Bash handles Windows paths in arguments but PATH itself needs POSIX form.
            mock_path = directory.replace("\\", "/")
            if os.name == "nt":
                mock_path = "/" + mock_path[0].lower() + mock_path[2:]
            env = os.environ.copy()
            env.update(
                HYS_SMOKE_BASE_URL="https://localhost", HYS_SMOKE_INSECURE_LOCAL_TLS="1"
            )
            invocation = f'PATH="{mock_path}:/usr/bin:/bin:$PATH"; export PATH; sh scripts/smoke.sh'
            for published, missing, expected in [
                ("0", "0", 0),
                ("1", "0", 1),
                ("0", "1", 1),
            ]:
                env.update(HYS_MOCK_PUBLISHED=published, HYS_MOCK_MISSING=missing)
                result = subprocess.run(
                    [shell, "-c", invocation],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(
                    result.returncode,
                    expected,
                    "Synthetic shell parity case failed; output withheld",
                )


if __name__ == "__main__":
    unittest.main()
