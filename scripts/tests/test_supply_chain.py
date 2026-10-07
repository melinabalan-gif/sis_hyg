import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SupplyChainTests(unittest.TestCase):
    def test_unpinned_action_and_writable_permissions_rejected(self):
        module = load("supply_chain_check")
        self.assertTrue(
            module.check_workflow(
                {
                    "permissions": {"contents": "write"},
                    "jobs": {
                        "probe": {
                            "timeout-minutes": 5,
                            "steps": [{"uses": "actions/checkout@v5"}],
                        }
                    },
                }
            )
        )

    def test_pinned_action_and_read_only_permissions_allowed(self):
        module = load("supply_chain_check")
        self.assertEqual(
            module.check_workflow(
                {
                    "permissions": {"contents": "read"},
                    "jobs": {
                        "probe": {
                            "timeout-minutes": 5,
                            "steps": [{"uses": "actions/checkout@" + "a" * 40}],
                        }
                    },
                }
            ),
            [],
        )

    def test_unknown_or_disallowed_license_rejected(self):
        module = load("supply_chain_check")
        self.assertTrue(
            module.check_licenses(
                {"packages": {"node_modules/probe": {"license": "GPL-3.0"}}}
            )
        )
        self.assertTrue(module.check_licenses({"packages": {"node_modules/probe": {}}}))
        self.assertEqual(
            module.check_licenses(
                {"packages": {"node_modules/probe": {"license": "MIT"}}}
            ),
            [],
        )


class RestoreGuardTests(unittest.TestCase):
    def test_restore_refuses_remote_or_non_synthetic_database(self):
        module = load("restore_drill")
        for url in [
            "postgresql://localhost/production",
            "postgresql://remote.test/drill_restore_test",
        ]:
            with self.assertRaises(ValueError):
                module.connection(url, target=True)

    def test_restore_only_accepts_explicit_loopback_test_target(self):
        module = load("restore_drill")
        self.assertEqual(
            module.connection(
                "postgresql://127.0.0.1:55432/drill_restore_test", target=True
            )["dbname"],
            "drill_restore_test",
        )


if __name__ == "__main__":
    unittest.main()
