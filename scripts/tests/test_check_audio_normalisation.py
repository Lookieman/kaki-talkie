# v1.0 | 06-Sep-2026 | Verify owner CLI success, argument validation and safe failures.
"""Exercise the real owner CLI in temporary directories without retaining outputs."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_audio_normalisation.py"
FIXTURE = ROOT / "backend/tests/fixtures/audio/chrome-tone.webm"


class AudioCliTests(unittest.TestCase):
    """Keep manual validation discoverable and prevent accidental overwrite."""

    def test_help_and_required_arguments(self) -> None:
        """Both help forms succeed; missing arguments fail with usage guidance."""
        for flag in ("-h", "--help"):
            result = subprocess.run([sys.executable, str(SCRIPT), flag], capture_output=True)
            self.assertEqual(result.returncode, 0)
            self.assertIn(b"--output", result.stdout)
        self.assertNotEqual(subprocess.run([sys.executable, str(SCRIPT)],
                                          capture_output=True).returncode, 0)

    def test_conversion_and_no_overwrite(self) -> None:
        """Create a WAV once and preserve existing data on subsequent attempts."""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output.wav"
            command = [sys.executable, str(SCRIPT), "--input", str(FIXTURE),
                       "--output", str(output)]
            result = subprocess.run(command, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b"16000 Hz", result.stdout)
            original = output.read_bytes()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), original)

    def test_invalid_input_does_not_create_output(self) -> None:
        """Malformed input fails before opening the output file."""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output.wav"
            result = subprocess.run([sys.executable, str(SCRIPT), "--input", str(SCRIPT),
                                     "--output", str(output)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
