# v1.0 | 18-Sep-2026 | WP6.6 loopback admin script: usage, token guard, exact requests.
"""Prove the curl fallback's shape without a backend (WP6-AT-18's tier A half).

A stub `curl` on the PATH records every invocation and answers HTTP 200, so
the tests assert exactly which endpoints, methods, headers and bodies the
script sends. The live loopback proof runs in `wp6_6_evidence.sh` Test 2.
"""

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/wp6_6_admin.sh"

STUB_CURL = """#!/usr/bin/env bash
# Record the invocation, write an empty JSON body, answer HTTP 200.
printf '%s\\n' "$*" >> "$CURL_LOG"
output=""
next=0
for argument in "$@"; do
    if [ "$next" = 1 ]; then output="$argument"; next=0; fi
    [ "$argument" = "-o" ] && next=1
done
[ -z "$output" ] || printf '{}' > "$output"
printf '200'
"""


def run_script(*arguments: str, token: str | None = "test-token",
               curl_log: Path | None = None) -> subprocess.CompletedProcess:
    """Run the script with a controlled environment and an optional stub curl."""
    environment = {**os.environ}
    environment.pop("KAKI_ADMIN_TOKEN", None)
    environment.pop("KAKI_ADMIN_DEFAULT_DEVICE", None)
    if token is not None:
        environment["KAKI_ADMIN_TOKEN"] = token
    if curl_log is not None:
        stub_directory = curl_log.parent
        stub = stub_directory / "curl"
        stub.write_text(STUB_CURL, encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        environment["PATH"] = f"{stub_directory}:{environment['PATH']}"
        environment["CURL_LOG"] = str(curl_log)
    return subprocess.run(
        [str(SCRIPT), *arguments], capture_output=True, text=True,
        timeout=60, env=environment, cwd=ROOT,
    )


class UsageTests(unittest.TestCase):
    def test_help_prints_usage_and_exits_zero(self):
        completed = run_script("--help")
        self.assertEqual(completed.returncode, 0)
        self.assertIn("config <en|ms|auto>", completed.stdout)
        self.assertIn("WP6-AT-18", completed.stdout)

    def test_bad_arguments_exit_2_without_calling_curl(self):
        log = Path(tempfile.mkdtemp(prefix="kaki-admin-test.")) / "curl.log"
        for arguments in ((), ("frobnicate",), ("config",), ("config", "zh"),
                          ("push", "--device")):
            with self.subTest(arguments=arguments):
                completed = run_script(*arguments, curl_log=log)
                self.assertEqual(completed.returncode, 2)
        self.assertFalse(log.exists())

    def test_a_missing_token_fails_closed_with_guidance(self):
        completed = run_script("state", token=None)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("KAKI_ADMIN_TOKEN", completed.stderr)


class RequestShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.log = Path(tempfile.mkdtemp(prefix="kaki-admin-test.")) / "curl.log"

    def calls(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines()

    def test_config_posts_the_language_and_device_with_the_bearer_token(self):
        completed = run_script("config", "ms", "--device", "kaki-pi-01", curl_log=self.log)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        call = self.calls()[0]
        self.assertIn("-X POST", call)
        self.assertIn("http://127.0.0.1:8000/api/admin/config", call)
        self.assertIn("Authorization: Bearer test-token", call)
        body = json.loads(call.split(" -d ", 1)[1].split(" -o ")[0])
        self.assertEqual(body, {"device_id": "kaki-pi-01", "reply_language": "ms"})

    def test_push_defaults_the_device_and_names_it_explicitly(self):
        completed = run_script("push", curl_log=self.log)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        call = self.calls()[0]
        self.assertIn("/api/admin/push", call)
        self.assertIn('"device_id": "kaki-pi-01"', call)

    def test_state_is_a_get_with_the_token_and_no_body(self):
        completed = run_script("state", curl_log=self.log)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        call = self.calls()[0]
        self.assertIn("-X GET", call)
        self.assertIn("/api/admin/state", call)
        self.assertNotIn(" -d ", call)

    def test_the_three_actions_cover_exactly_the_three_admin_endpoints(self):
        run_script("config", "auto", curl_log=self.log)
        run_script("push", curl_log=self.log)
        run_script("state", curl_log=self.log)
        endpoints = {call.split("http://127.0.0.1:8000", 1)[1].split()[0]
                     for call in self.calls()}
        self.assertEqual(endpoints,
                         {"/api/admin/config", "/api/admin/push", "/api/admin/state"})


if __name__ == "__main__":
    unittest.main()
