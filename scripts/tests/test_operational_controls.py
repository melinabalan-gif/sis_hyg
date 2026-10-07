"""Synthetic, isolated regression tests for repository safety controls."""

import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "policy", ROOT / "scripts/policy_check.py"
)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class PolicyTests(unittest.TestCase):
    def test_known_token_shapes_are_detected(self):
        for text in [
            "ghp_" + "a" * 36,
            "AKIA" + "A" * 16,
            "-----BEGIN " + "PRIVATE KEY-----",
            "token = '" + "a" * 32 + "'",
            "postgresql://owner:" + "a" * 20 + "@host/db",
        ]:
            with self.subTest(kind=text[:5]):
                self.assertIn("secret", policy.detect(text, []))

    def test_explicit_identity_fields_are_detected(self):
        for text in [
            'dni = "' + "12" + "345678" + '"',
            'cuil: "' + "20-12345678-3" + '"',
            'email: "' + "person@" + 'real.test"',
        ]:
            self.assertIn("pii", policy.detect(text, []))

    def test_synthetic_placeholders_and_documentation_are_allowed(self):
        for text in [
            'password="CHANGE_ME_EXAMPLE_LONG"',
            'password="synthetic_password"',
            'email="operator@example.invalid"',
            "DNI/CUIL must not be stored in cleartext.",
            'secret="${S3_SECRET_KEY}"',
        ]:
            self.assertEqual(policy.detect(text, []), [])

    def test_restricted_terms_are_case_insensitive(self):
        self.assertIn(
            "restricted",
            policy.detect("SYNTHETIC_RESTRICTED_PROBE", ["synthetic_restricted_probe"]),
        )

    def test_json_and_unquoted_yaml_credentials_are_detected(self):
        for text in ['{"password": "' + "z" * 24 + '"}', "password: " + "z" * 24]:
            self.assertIn("secret", policy.detect(text, []))

    def test_variable_assignments_are_not_credentials(self):
        self.assertEqual(policy.detect("const token = generation.current;", []), [])

    def test_invalid_restricted_configuration_fails_without_value(self):
        with (
            patch.dict(os.environ, {"HYS_RESTRICTED_TERMS_B64": "%%%"}),
            self.assertRaises(SystemExit) as error,
        ):
            policy.protected_terms()
        self.assertNotIn("%%%", str(error.exception))

    def test_history_detects_removed_secret_and_does_not_echo_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", directory], check=True)
            token = "ghp_" + "z" * 36
            (root / "old.txt").write_text(token)
            subprocess.run(["git", "-C", directory, "add", "."], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    directory,
                    "-c",
                    "user.name=Synthetic",
                    "-c",
                    "user.email=synthetic@example.invalid",
                    "commit",
                    "-qm",
                    "synthetic",
                ],
                check=True,
            )
            (root / "old.txt").unlink()
            failures = policy.scan_repository(root, [], history=True)
            self.assertTrue(
                any(
                    "history" in failure and "secret" in failure for failure in failures
                )
            )
            self.assertNotIn(token, str(failures))

    def test_ignored_local_artifacts_are_not_scanned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", directory], check=True)
            (root / ".gitignore").write_text(".env\n.atl/\n*.backup*\n")
            (root / ".env").write_text("ghp_" + "z" * 36)
            (root / ".atl").mkdir()
            (root / ".atl/probe.md").write_text("ghp_" + "z" * 36)
            self.assertEqual(policy.scan_repository(root, [], history=False), [])

    def test_tracked_private_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", directory], check=True)
            (root / "source.docx").write_bytes(b"synthetic")
            self.assertTrue(
                any(
                    "artifact" in failure
                    for failure in policy.scan_repository(root, [], history=False)
                )
            )


class OperationalWiringTests(unittest.TestCase):
    def test_ci_has_effective_controls_not_only_claims(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        for command in [
            "policy_check.py --history",
            "test_operational_controls",
            "pip-audit==",
            "alembic heads",
            "test:lint",
            "test:e2e",
            "npm sbom",
            "supply_chain_check.py",
        ]:
            self.assertIn(command, workflow)
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("contents: read", workflow)

    def test_caddy_blocks_framing_and_limits_csp_without_unsafe_eval(self):
        caddy = (ROOT / "infra/caddy/Caddyfile").read_text()
        self.assertIn("Content-Security-Policy", caddy)
        self.assertIn("frame-ancestors 'none'", caddy)
        self.assertIn("object-src 'none'", caddy)
        self.assertNotIn("unsafe-eval", caddy)
        self.assertIn("X-Frame-Options", caddy)
        self.assertNotIn("rate_limit", caddy)


if __name__ == "__main__":
    unittest.main()
