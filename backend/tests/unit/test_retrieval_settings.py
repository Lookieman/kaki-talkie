# v1.1 | 12-Sep-2026 | Guard the settings tests against ambient KAKI_* exports.
# v1.0 | 11-Sep-2026 | Verify retrieval configuration keeps canned as the safe default.
"""Exercise RetrievalSettings; the real adapter and model are never loaded here."""

import unittest

from kaki_backend.config import APPROVED_EMBEDDING_MODEL, RetrievalSettings
from kaki_backend.orchestration.canned_ports import CannedRetrieverPort
from kaki_test_env import CannedEnvironment  #v1.1


class RetrievalSettingsTest(CannedEnvironment, unittest.TestCase):  #v1.1
    """Environment selection: canned default, guarded rag mode, normalise switch."""

    def test_defaults_remain_canned_inert_and_ready(self):
        settings = RetrievalSettings.from_environment({})
        self.assertEqual((settings.mode, settings.active), ("canned", False))
        self.assertTrue(settings.normalise)
        self.assertEqual(settings.embedding_model, APPROVED_EMBEDDING_MODEL)
        port = settings.create_port()
        self.assertIsInstance(port, CannedRetrieverPort)
        self.assertTrue(port.ready())
        self.assertEqual(port.retrieve("anything", None), ())

    def test_rag_mode_requires_an_absolute_data_root(self):
        settings = RetrievalSettings.from_environment(
            {"KAKI_RETRIEVAL_MODE": "rag", "KAKI_DATA_ROOT": "/data/kaki"}
        )
        self.assertTrue(settings.active)
        self.assertEqual(settings.data_root, "/data/kaki")
        for env in (
            {"KAKI_RETRIEVAL_MODE": "rag"},
            {"KAKI_RETRIEVAL_MODE": "rag", "KAKI_DATA_ROOT": "relative/path"},
            {"KAKI_RETRIEVAL_MODE": "chroma"},
        ):
            with self.assertRaises(ValueError, msg=env):
                RetrievalSettings.from_environment(env)

    def test_normalise_switch_parses_and_rejects_unknown_values(self):
        settings = RetrievalSettings.from_environment({"KAKI_QUERY_NORMALISE": "off"})
        self.assertFalse(settings.normalise)
        with self.assertRaises(ValueError):
            RetrievalSettings.from_environment({"KAKI_QUERY_NORMALISE": "maybe"})


if __name__ == "__main__":
    unittest.main()
