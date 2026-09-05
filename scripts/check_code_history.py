# v1.0 | 05-Sep-2026 | Check language-valid histories, changed markers and runtime paths.

import argparse  #v1.0
import difflib  #v1.0
import io  #v1.0
import os  #v1.0
import re  #v1.0
import subprocess  #v1.0
import tokenize  #v1.0
from datetime import datetime  #v1.0
from pathlib import Path  #v1.0

ROOT = Path(__file__).resolve().parents[1]  #v1.0
HASH_LANGUAGES = {".py", ".sh", ".yaml", ".yml", ".toml"}  #v1.0
SLASH_LANGUAGES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}  #v1.0
GENERATED = {"apps/web/next-env.d.ts"}  #v1.0
ENTRY = re.compile(r"(v\d+\.\d+) \| (\d{2}-[A-Z][a-z]{2}-\d{4}) \| (.+)")  #v1.0


def git(*arguments: str) -> str:  #v1.0
    result = subprocess.run(  #v1.0
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, encoding="utf-8"  #v1.0
    )  #v1.0
    return result.stdout  #v1.0


def supported(path: str) -> bool:  #v1.0
    return path not in GENERATED and Path(path).suffix in HASH_LANGUAGES | SLASH_LANGUAGES | {  #v1.0
        ".css"  #v1.0
    }  #v1.0


def comment_map(path: str, source: str) -> tuple[dict[int, str], set[int]]:  #v1.0
    comments = {}  #v1.0
    code = set()  #v1.0
    if Path(path).suffix == ".py":  #v1.0
        for token in tokenize.generate_tokens(io.StringIO(source).readline):  #v1.0
            if token.type == tokenize.COMMENT:  #v1.0
                comments[token.start[0]] = token.string  #v1.0
            elif token.type not in {  #v1.0
                tokenize.ENDMARKER,  #v1.0
                tokenize.INDENT,  #v1.0
                tokenize.DEDENT,  #v1.0
                tokenize.NEWLINE,  #v1.0
                tokenize.NL,  #v1.0
                tokenize.ENCODING,  #v1.0
            }:  #v1.0
                code.add(token.end[0])  #v1.0
        return comments, code  #v1.0
    hash_style = Path(path).suffix in HASH_LANGUAGES  #v1.0
    css = Path(path).suffix == ".css"  #v1.0
    quote = ""  #v1.0
    block = False  #v1.0
    escaped = False  #v1.0
    for number, line in enumerate(source.splitlines(), 1):  #v1.0
        index = 0  #v1.0
        while index < len(line):  #v1.0
            character = line[index]  #v1.0
            if block:  #v1.0
                end = line.find("*/", index)  #v1.0
                if end < 0:  #v1.0
                    break  #v1.0
                block = False  #v1.0
                index = end + 2  #v1.0
                continue  #v1.0
            if quote:  #v1.0
                if escaped:  #v1.0
                    escaped = False  #v1.0
                elif character == "\\":  #v1.0
                    escaped = True  #v1.0
                elif character == quote:  #v1.0
                    quote = ""  #v1.0
                index += 1  #v1.0
                continue  #v1.0
            if character in "\"'`":  #v1.0
                quote = character  #v1.0
                code.add(number)  #v1.0
            elif (hash_style and character == "#") or (  #v1.0
                not hash_style and line[index : index + 2] == "//"  #v1.0
            ):  #v1.0
                if not css or character == "#":  #v1.0
                    comments[number] = line[index:]  #v1.0
                    break  #v1.0
            elif not hash_style and line[index : index + 2] == "/*":  #v1.0
                end = line.find("*/", index + 2)  #v1.0
                if end < 0:  #v1.0
                    block = True  #v1.0
                    break  #v1.0
                comments[number] = line[index : end + 2]  #v1.0
                index = end + 2  #v1.0
                continue  #v1.0
            elif not character.isspace():  #v1.0
                code.add(number)  #v1.0
            index += 1  #v1.0
        escaped = False  #v1.0
    return comments, code  #v1.0


def history(path: str, source: str) -> list[tuple[str, str, str]]:  #v1.0
    prefix, suffix = ("# ", "")  #v1.0
    if Path(path).suffix in SLASH_LANGUAGES:  #v1.0
        prefix = "// "  #v1.0
    elif Path(path).suffix == ".css":  #v1.0
        prefix, suffix = "/* ", " */"  #v1.0
    entries = []  #v1.0
    lines = source.splitlines()  #v1.0
    if lines and lines[0].startswith("#!"):  #v1.0
        lines = lines[1:]  #v1.0
    for line in lines:  #v1.0
        if not line.startswith(prefix) or (suffix and not line.endswith(suffix)):  #v1.0
            break  #v1.0
        content = line[len(prefix) : len(line) - len(suffix) if suffix else None]  #v1.0
        match = ENTRY.fullmatch(content)  #v1.0
        if not match:  #v1.0
            break  #v1.0
        entries.append(match.groups())  #v1.0
    return entries  #v1.0


def check_text(path: str, source: str, previous: str | None) -> list[str]:  #v1.0
    if not supported(path):  #v1.0
        return []  #v1.0
    errors = []  #v1.0
    entries = history(path, source)  #v1.0
    if not entries:  #v1.0
        return [f"{path}: missing language-valid history at the top"]  #v1.0
    versions = []  #v1.0
    for version, date, description in entries:  #v1.0
        versions.append(tuple(int(part) for part in version[1:].split(".")))  #v1.0
        try:  #v1.0
            datetime.strptime(date, "%d-%b-%Y")  #v1.0
        except ValueError:  #v1.0
            errors.append(f"{path}: invalid history date {date}")  #v1.0
    if versions != sorted(set(versions), reverse=True):  #v1.0
        errors.append(f"{path}: history must have distinct versions newest first")  #v1.0
    old_entries = history(path, previous or "")  #v1.0
    if previous is not None and source != previous and old_entries:  #v1.0
        if entries[0][0] == old_entries[0][0] or entries[-len(old_entries):] != old_entries:  #v1.0
            errors.append(f"{path}: prepend newer history entries and preserve previous entries")  #v1.0
    comments, code = comment_map(path, source)  #v1.0
    lines = source.splitlines()  #v1.0
    changed = set()  #v1.0
    matcher = difflib.SequenceMatcher(a=(previous or "").splitlines(), b=lines, autojunk=False)  #v1.0
    for operation, _, _, start, end in matcher.get_opcodes():  #v1.0
        if operation in {"insert", "replace"}:  #v1.0
            changed.update(range(start + 1, end + 1))  #v1.0
    introduced = {entry[0] for entry in entries} - {entry[0] for entry in old_entries}  #v1.0
    if Path(path).suffix in SLASH_LANGUAGES:  #v1.0
        expected = {"//" + version for version in introduced}  #v1.0
    elif Path(path).suffix == ".css":  #v1.0
        expected = {"/* " + version + " */" for version in introduced}  #v1.0
    else:  #v1.0
        expected = {"#" + version for version in introduced}  #v1.0
    for number in sorted(changed & code):  #v1.0
        if comments.get(number, "").strip() not in expected:  #v1.0
            tags = ", ".join(sorted(expected)) or "a newly recorded version marker"  #v1.0
            errors.append(f"{path}:{number}: changed code needs {tags}")  #v1.0
    if previous is not None:  #v1.0
        old_comments, old_code = comment_map(path, previous)  #v1.0
        old_lines = previous.splitlines()  #v1.0
        old_bodies = [  #v1.0
            line.rsplit(old_comments[n], 1)[0].rstrip() if n in old_comments else line.rstrip()  #v1.0
            for n, line in enumerate(old_lines, 1)  #v1.0
        ]  #v1.0
        new_bodies = [  #v1.0
            line.rsplit(comments[n], 1)[0].rstrip() if n in comments else line.rstrip()  #v1.0
            for n, line in enumerate(lines, 1)  #v1.0
        ]  #v1.0
        body_matcher = difflib.SequenceMatcher(a=old_bodies, b=new_bodies, autojunk=False)  #v1.0
        for old_start, new_start, length in body_matcher.get_matching_blocks():  #v1.0
            for offset in range(length):  #v1.0
                number = new_start + offset + 1  #v1.0
                if (  #v1.0
                    number in changed & code  #v1.0
                    and old_start + offset + 1 in old_code  #v1.0
                    and comments.get(number, "").strip() in expected  #v1.0
                ):  #v1.0
                    errors.append(f"{path}:{number}: do not retag unchanged code")  #v1.0
    return errors  #v1.0


def forbidden_path(path: str) -> bool:  #v1.0
    name = Path(path).name.lower()  #v1.0
    parts = set(Path(path).parts)  #v1.0
    return (  #v1.0
        (name.startswith(".env") and name != ".env.example")  #v1.0
        or bool(re.search(r"\.(?:sqlite3?|db)(?:-shm|-wal)?$", name))  #v1.0
        or name.endswith((".pem", ".key", ".p12", ".pfx"))  #v1.0
        or bool(re.match(r"(?:credentials|secrets|service[-_]account)(?:[.-].*)?\.json$", name))  #v1.0
        or bool(  #v1.0
            parts  #v1.0
            & {  #v1.0
                ".cloudflared",  #v1.0
                ".tokens",  #v1.0
                "recordings",  #v1.0
                "runtime_audio",  #v1.0
                "chroma",  #v1.0
                "chroma_db",  #v1.0
                "runtime-data",  #v1.0
                "kaki-talkie-data",  #v1.0
            }  #v1.0
        )  #v1.0
        or path.startswith(("rag/corpus/snapshots/", "rag/corpus/processed/"))  #v1.0
    )  #v1.0


def main() -> int:  #v1.0
    parser = argparse.ArgumentParser(description="WP1 code history and tracked-path checks")  #v1.0
    parser.add_argument("--base", default=os.environ.get("HISTORY_BASE") or "HEAD")  #v1.0
    options = parser.parse_args()  #v1.0
    base_ref = options.base  #v1.0
    if base_ref and set(base_ref) == {"0"}:  #v1.0
        base_ref = git("merge-base", "HEAD", "origin/main").strip()  #v1.0
    base = git("rev-parse", "--verify", base_ref + "^{commit}").strip()  #v1.0
    paths = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0")  #v1.0
    old_paths = set(git("ls-tree", "-r", "--name-only", "-z", base).split("\0"))  #v1.0
    errors = []  #v1.0
    count = 0  #v1.0
    for path in sorted(set(paths) - {""}):  #v1.0
        if forbidden_path(path):  #v1.0
            errors.append(f"{path}: secret-bearing or runtime-data path must not be tracked")  #v1.0
        if not supported(path) or not (ROOT / path).is_file():  #v1.0
            continue  #v1.0
        source = (ROOT / path).read_text(encoding="utf-8")  #v1.0
        previous = git("show", f"{base}:{path}") if path in old_paths else None  #v1.0
        errors.extend(check_text(path, source, previous))  #v1.0
        count += 1  #v1.0
    for error in errors:  #v1.0
        print(error)  #v1.0
    print(f"Checked {count} source files against {base}: {len(errors)} error(s)")  #v1.0
    return 1 if errors else 0  #v1.0


if __name__ == "__main__":  #v1.0
    raise SystemExit(main())  #v1.0
