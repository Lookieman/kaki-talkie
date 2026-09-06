# v1.1 | 06-Sep-2026 | Distinguish initial headers from later changed-line markers.
# v1.0 | 05-Sep-2026 | Exercise history validation and secret/runtime path exclusions.

"""Verify initial-file exemptions and preserve history and path safeguards."""  #v1.1

import sys  #v1.0
import unittest  #v1.0
from pathlib import Path  #v1.0

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  #v1.0

from check_code_history import check_text, forbidden_path  #v1.0

PY_HEADER = "# v1.0 | 05-Sep-2026 | First version\n"  #v1.0
NEW_HEADER = "# v1.1 | 05-Sep-2026 | Update value\n"  #v1.0


class HistoryTests(unittest.TestCase):  #v1.0
    def test_valid_new_python_and_multiline_expression(self) -> None:  #v1.0
        body = "value = (  #v1.0\n    1 + 2  #v1.0\n)  #v1.0\n"  #v1.0
        self.assertEqual(check_text("example.py", PY_HEADER + body, None), [])  #v1.0

    def test_python_string_is_not_a_version_comment(self) -> None:  #v1.0
        source = NEW_HEADER + PY_HEADER + 'value = "#v1.1"\n'  #v1.1
        self.assertTrue(check_text("example.py", source, PY_HEADER + "value = 1\n"))  #v1.1

    def test_existing_untouched_code_does_not_need_new_tags(self) -> None:  #v1.0
        old = PY_HEADER + "value = 1\nother = 2\n"  #v1.0
        new = NEW_HEADER + PY_HEADER + "value = 3  #v1.1\nother = 2\n"  #v1.0
        self.assertEqual(check_text("example.py", new, old), [])  #v1.0

    def test_new_tag_on_unchanged_code_is_rejected(self) -> None:  #v1.0
        old = PY_HEADER + "value = 1\n"  #v1.0
        new = NEW_HEADER + PY_HEADER + "value = 1  #v1.1\n"  #v1.0
        self.assertIn("retag unchanged", " ".join(check_text("example.py", new, old)))  #v1.0

    def test_duplicate_line_in_a_new_function_is_not_an_unchanged_line(self) -> None:  #v1.0
        old = PY_HEADER + "def first():\n    return 1\n"  #v1.0
        new = NEW_HEADER + old + "\ndef second():  #v1.1\n    return 1  #v1.1\n"  #v1.0
        self.assertEqual(check_text("example.py", new, old), [])  #v1.0

    def test_changed_line_cannot_keep_old_version(self) -> None:  #v1.0
        old = PY_HEADER + "value = 1\n"  #v1.0
        new = NEW_HEADER + PY_HEADER + "value = 2  #v1.0\n"  #v1.0
        self.assertIn("needs #v1.1", " ".join(check_text("example.py", new, old)))  #v1.0

    def test_multiple_recorded_versions_in_a_pull_request_keep_their_tags(self) -> None:  #v1.0
        old = PY_HEADER + "value = 1\n"  #v1.0
        latest = "# v1.2 | 05-Sep-2026 | Add another value\n"  #v1.0
        new = latest + NEW_HEADER + PY_HEADER + "value = 2  #v1.1\nother = 3  #v1.2\n"  #v1.0
        self.assertEqual(check_text("example.py", new, old), [])  #v1.0

    def test_missing_update_and_removed_history_fail(self) -> None:  #v1.0
        old = PY_HEADER + "value = 1\n"  #v1.0
        for new in (PY_HEADER + "value = 2  #v1.0\n", NEW_HEADER + "value = 2  #v1.1\n"):  #v1.0
            self.assertTrue(check_text("example.py", new, old))  #v1.0

    def test_invalid_date_and_out_of_order_versions_fail(self) -> None:  #v1.0
        for header in (PY_HEADER.replace("05-Sep", "31-Feb"), PY_HEADER + NEW_HEADER):  #v1.0
            self.assertTrue(check_text("example.py", header + "value = 1  #v1.0\n", None))  #v1.0

    def test_all_js_family_extensions_use_actual_slash_comments(self) -> None:  #v1.0
        for extension in ("ts", "tsx", "js", "jsx", "mjs", "cjs"):  #v1.0
            path = "example." + extension  #v1.0
            header = "// v1.0 | 05-Sep-2026 | First version\n"  #v1.0
            self.assertEqual(  #v1.0
                check_text(path, header + 'const x = "https://test"; //v1.0\n', None), []  #v1.0
            )  #v1.0
            update = NEW_HEADER.replace("# ", "// ") + header  #v1.1
            self.assertTrue(check_text(path, update + 'const x = "//v1.1";\n', header + "const x = 1;\n"))  #v1.1
            self.assertTrue(check_text(path, PY_HEADER + "const x = 1; //v1.0\n", None))  #v1.0

    def test_css_uses_block_comments_and_ignores_strings(self) -> None:  #v1.0
        header = "/* v1.0 | 05-Sep-2026 | First version */\n"  #v1.0
        good = header + '.x { content: "/* v1.0 */"; } /* v1.0 */\n'  #v1.0
        self.assertEqual(check_text("example.css", good, None), [])  #v1.0
        update = "/* v1.1 | 06-Sep-2026 | Change content */\n" + header  #v1.1
        bad = update + '.x { content: "/* v1.1 */"; }\n'  #v1.1
        self.assertTrue(check_text("example.css", bad, good))  #v1.1

    def test_yaml_toml_and_shell_use_hash_comments(self) -> None:  #v1.0
        for extension, body in (  #v1.0
            ("yaml", "value: 'a#b' #v1.0\n"),  #v1.0
            ("yml", "value: 1 #v1.0\n"),  #v1.0
            ("toml", "value = 1 #v1.0\n"),  #v1.0
            ("sh", "echo 'hello' #v1.0\n"),  #v1.0
        ):  #v1.0
            self.assertEqual(check_text("example." + extension, PY_HEADER + body, None), [])  #v1.0
        self.assertTrue(check_text("example.yaml", NEW_HEADER + PY_HEADER + 'value: "#v1.1"\n', PY_HEADER + "value: 1\n"))  #v1.1

    def test_shebang_before_history_is_valid(self) -> None:  #v1.0
        source = "#!/usr/bin/env python3\n" + PY_HEADER + "value = 1  #v1.0\n"  #v1.0
        self.assertEqual(check_text("example.py", source, None), [])  #v1.0

    def test_no_comments_added_to_excluded_formats(self) -> None:  #v1.0
        for path in (  #v1.0
            "package.json",  #v1.0
            "package-lock.json",  #v1.0
            "uv.lock",  #v1.0
            "README.md",  #v1.0
            "speech.wav",  #v1.0
            "image.png",  #v1.0
            "apps/web/next-env.d.ts",  #v1.0
        ):  #v1.0
            self.assertEqual(check_text(path, "no history", None), [])  #v1.0

    def test_bad_markers_do_not_pass(self) -> None:  #v1.0
        for marker in ("#changed", "# v1.1", "#v1.1 modified here", "#v2.0"):  #v1.1
            self.assertTrue(check_text("example.py", NEW_HEADER + PY_HEADER + "x = 2  " + marker, PY_HEADER + "x = 1\n"))  #v1.1

    def test_initial_headers_and_later_markers_across_languages(self) -> None:  #v1.1
        """New files need headers; subsequent edits need actual current markers."""  #v1.1
        for extension, prefix, suffix, initial, edited, marker in (  #v1.1
            ("py", "# ", "", "value = (\n    1 + 2\n)\n", "value = 4", "#v1.1"),  #v1.1
            *((ext, "// ", "", "const x = 1;\n", "const x = 2;", "//v1.1")  #v1.1
              for ext in ("js", "jsx", "ts", "tsx", "mjs", "cjs")),  #v1.1
            ("css", "/* ", " */", ".x { color: red; }\n", ".x { color: blue; }", "/* v1.1 */"),  #v1.1
            ("yaml", "# ", "", "value: 1\n", "value: 2", "#v1.1"),  #v1.1
            ("yml", "# ", "", "value: 1\n", "value: 2", "#v1.1"),  #v1.1
            ("toml", "# ", "", "value = 1\n", "value = 2", "#v1.1"),  #v1.1
            ("sh", "# ", "", "echo hello\n", "echo goodbye", "#v1.1"),  #v1.1
        ):  #v1.1
            with self.subTest(extension=extension):  #v1.1
                path = "example." + extension  #v1.1
                header = prefix + "v1.0 | 05-Sep-2026 | Initial version" + suffix + "\n"  #v1.1
                update = prefix + "v1.1 | 06-Sep-2026 | Edit value" + suffix + "\n"  #v1.1
                old = header + initial  #v1.1
                self.assertEqual(check_text(path, old, None), [])  #v1.1
                self.assertIn("missing language-valid history", " ".join(check_text(path, initial, None)))  #v1.1
                new = update + header + edited  #v1.1
                self.assertIn("changed code needs", " ".join(check_text(path, new, old)))  #v1.1
                self.assertEqual(check_text(path, new + "  " + marker + "\n", old), [])  #v1.1

    def test_existing_empty_file_still_requires_changed_markers(self) -> None:  #v1.1
        """An empty baseline file is existing, rather than newly created."""  #v1.1
        self.assertIn("needs #v1.0", " ".join(check_text("example.py", PY_HEADER + "x = 1\n", "")))  #v1.1

    def test_runtime_paths_and_credentials_are_rejected(self) -> None:  #v1.0
        for path in (  #v1.0
            ".env",  #v1.0
            "backend/.env.production",  #v1.0
            "credentials.json",  #v1.0
            "credentials-demo.json",  #v1.0
            "service-account.json",  #v1.0
            "data/turns.sqlite3-wal",  #v1.0
            ".cloudflared/config.yml",  #v1.0
            "rag/corpus/snapshots/sample.md",  #v1.0
        ):  #v1.0
            self.assertTrue(forbidden_path(path), path)  #v1.0
        for path in (  #v1.0
            ".env.example",  #v1.0
            "backend/src/kaki_backend/fixtures/canned_reply.wav",  #v1.0
            "backend/tests/contract/snapshots/turn_response.schema.json",  #v1.0
        ):  #v1.0
            self.assertFalse(forbidden_path(path), path)  #v1.0


if __name__ == "__main__":  #v1.0
    unittest.main()  #v1.0
