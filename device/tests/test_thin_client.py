# v1.0 | 16-Sep-2026 | WP6-AT-13 thin-client inspection, run as a test so CI gates it.
"""Prove the device holds no model, retrieval, prompt, case or SQL logic.

WP6-AT-13 is an owner gate run through `wp_check.py --unit WP6.1 --tier A`.
The same inspection runs here so a violation fails CI the moment it lands,
rather than at the gate. Both call one implementation, `thin_client_findings`,
so the gate and the suite can never drift apart.

The last test is the important one: it plants each violation in a copy of the
package and proves the inspection catches it. An inspection nobody has seen
fail is not evidence.
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

DEVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEVICE_ROOT.parent / "scripts"))

from wp_check import thin_client_findings  # noqa: E402


class ThinClientTests(unittest.TestCase):
    """The shipped package passes every rule."""

    def test_the_device_package_has_no_findings(self):
        findings = thin_client_findings(DEVICE_ROOT)
        for rule, found in findings.items():
            with self.subTest(rule=rule):
                self.assertEqual(found, [], f"{rule}: {found}")

    def test_no_backend_rag_or_model_module_is_importable_from_the_device(self):
        # A blunt second reading of the same property, independent of the AST walk.
        forbidden = ("kaki_backend", "kaki_rag", "chromadb", "mlx_lm", "sqlite3", "torch")
        for path in (DEVICE_ROOT / "src").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for name in forbidden:
                with self.subTest(path=path.name, module=name):
                    self.assertNotIn(f"import {name}", text)


class InspectionCatchesViolationsTests(unittest.TestCase):
    """Each rule fails when the violation it describes is planted."""

    def copy_package(self) -> Path:
        """Copy device/src and pyproject.toml into a scratch directory."""
        scratch = Path(tempfile.mkdtemp(prefix="kaki-thin-client."))
        shutil.copytree(DEVICE_ROOT / "src", scratch / "src")
        shutil.copy(DEVICE_ROOT / "pyproject.toml", scratch / "pyproject.toml")
        return scratch

    def plant(self, text: str) -> dict[str, list[str]]:
        """Append a line to a device module and return the resulting findings."""
        scratch = self.copy_package()
        target = scratch / "src/kaki_device/state_machine.py"
        target.write_text(target.read_text(encoding="utf-8") + text, encoding="utf-8")
        return thin_client_findings(scratch)

    def test_a_backend_import_is_caught(self):
        findings = self.plant("\nimport kaki_backend\n")
        self.assertTrue(findings["imports"])

    def test_an_unapproved_third_party_import_is_caught(self):
        findings = self.plant("\nimport requests\n")
        self.assertTrue(findings["imports"])

    def test_prompt_model_and_sql_text_is_caught(self):
        for planted in (
            '\nSYSTEM_PROMPT = "You are..."\n',
            '\nLLM = "http://127.0.0.1:8082"\n',
            '\nQUERY = "INSERT INTO turns VALUES (1)"\n',
        ):
            with self.subTest(planted=planted.strip()[:24]):
                self.assertTrue(self.plant(planted)["tokens"])

    def test_a_request_to_a_model_service_path_is_caught(self):
        findings = self.plant('\nPATH = "/v1/chat/completions"\n')
        self.assertTrue(findings["paths"] or findings["tokens"])

    def test_a_non_device_environment_variable_is_caught(self):
        findings = self.plant('\nMODE = "KAKI_LLM_MODE"\n')
        self.assertTrue(findings["environment"])

    def test_an_unapproved_runtime_dependency_is_caught(self):
        scratch = self.copy_package()
        manifest = scratch / "pyproject.toml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace(
                'dependencies = ["httpx>=0.27,<1"]',
                'dependencies = ["httpx>=0.27,<1", "transformers>=4.51"]',
            ),
            encoding="utf-8",
        )
        self.assertTrue(thin_client_findings(scratch)["dependencies"])


if __name__ == "__main__":
    unittest.main()
