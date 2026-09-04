# v1.0 | 04-Sep-2026 | Lock the WP1 turn-response JSON schema snapshot.

import json
from pathlib import Path
import unittest

from kaki_backend.contracts.responses import TurnResponse


class TurnSchemaSnapshotTests(unittest.TestCase):
    def test_turn_response_schema_matches_snapshot(self) -> None:
        snapshot_path = Path(__file__).parent / "snapshots" / "turn_response.schema.json"
        expected_schema = json.loads(snapshot_path.read_text(encoding="utf-8"))

        self.assertEqual(TurnResponse.model_json_schema(), expected_schema)


if __name__ == "__main__":
    unittest.main()
