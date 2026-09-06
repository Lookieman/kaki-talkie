# v1.1 | 06-Sep-2026 | Document CLI use and strengthen validation and failure safety.
# v1.0 | 05-Sep-2026 | Remove a merged and pushed WP worktree and its local branch safely.

"""Remove one merged implementation-unit worktree after the owner has pushed main.

Run from clean main on the Windows development desktop. Fetches origin, then
removes the verified sibling checkout and its merged local feature branch. Git
may refuse removal for local files, including ignored files; no force or recursive
deletion fallback is used. Never commits, merges or pushes; remote branches and
the Codex project remain untouched. See docs/04-prototype/wp-validation-runbook.md.
"""  #v1.1

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


MAIN_BRANCH = "main"
REMOTE_NAME = "origin"


def run_command(
    command: list[str],
    cwd: Path,
    capture_output: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a command in cwd; raise RuntimeError on a checked non-zero exit."""  #v1.1
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=capture_output,
        check=False,
    )

    if check and result.returncode != 0:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: "
            f"{' '.join(command)}"
        )

    return result


def get_git_executable() -> str:
    """Return Git from PATH, or fail before attempting repository operations."""  #v1.1
    git_executable = shutil.which("git")

    if not git_executable:
        raise RuntimeError("Git was not found on PATH.")

    return git_executable


def get_repo_root(git_executable: str, start_path: Path) -> Path:
    """Resolve the checkout containing start_path; fail outside a Git repository."""  #v1.1
    result = run_command(
        [
            git_executable,
            "-C",
            str(start_path),
            "rev-parse",
            "--show-toplevel",
        ],
        cwd=start_path,
        capture_output=True,
    )

    return Path(result.stdout.strip()).resolve()


def get_current_branch(
    git_executable: str,
    repo_root: Path,
) -> str:
    """Return the checked-out branch name, or an empty string for detached HEAD."""  #v1.1
    result = run_command(
        [git_executable, "branch", "--show-current"],
        cwd=repo_root,
        capture_output=True,
    )

    return result.stdout.strip()


def ensure_clean_tree(
    git_executable: str,
    repo_root: Path,
    label: str,
) -> None:
    """Refuse cleanup when the labelled checkout has changes or untracked files."""  #v1.1
    result = run_command(
        [git_executable, "status", "--porcelain"],
        cwd=repo_root,
        capture_output=True,
    )

    if result.stdout.strip():
        raise RuntimeError(
            f"{label} is not clean. "
            "Commit, stash, or revert changes first."
        )


def ensure_main_matches_remote(
    git_executable: str,
    repo_root: Path,
) -> None:
    """Fetch origin/main and refuse to proceed unless local main matches it."""  #v1.1
    run_command(
        [git_executable, "fetch", REMOTE_NAME, MAIN_BRANCH],
        cwd=repo_root,
    )

    result = run_command(
        [
            git_executable,
            "rev-list",
            "--left-right",
            "--count",
            f"{MAIN_BRANCH}...{REMOTE_NAME}/{MAIN_BRANCH}",
        ],
        cwd=repo_root,
        capture_output=True,
    )

    counts = result.stdout.strip().split()

    if len(counts) != 2 or not all(count.isascii() and count.isdigit() for count in counts):  #v1.1
        raise RuntimeError(
            "Could not determine local/remote main status."
        )

    local_only = int(counts[0])
    remote_only = int(counts[1])

    if local_only != 0 or remote_only != 0:
        raise RuntimeError(
            "Local main and origin/main are not identical. "
            f"Local-only commits: {local_only}; "
            f"remote-only commits: {remote_only}. "
            "Merge and push the unit manually before cleanup."
        )


def parse_arguments() -> argparse.Namespace:
    """Parse CLI options; help exits zero and invalid usage exits non-zero."""  #v1.1
    parser = argparse.ArgumentParser(
        description=(
            "Safely remove a merged KaKi-Talkie "
            "implementation-unit worktree."
        ),  #v1.1
        epilog=(  #v1.1
            "Requires clean main matching origin/main and a clean, unlocked sibling worktree on feat/wpN-M-<slug>, fully merged into main. Fetches origin; removes that checkout and its local branch without force. Ignored files may prevent removal. Remote branches and the Codex project are retained. "  #v1.1
            "No automatic commit, merge or push. "  #v1.1
            "Example: python scripts/cleanup_wp_worktree.py --unit WP2.1. "  #v1.1
            "Guide: docs/04-prototype/wp-validation-runbook.md"  #v1.1
        ),  #v1.1
    )

    parser.add_argument(
        "--unit",
        required=True,
        help="Required unit in WPn.m form (case-insensitive), for example WP2.1.",  #v1.1
    )

    return parser.parse_args()


def main() -> int:
    """Validate prerequisites and perform the requested operation; return zero on success."""  #v1.1
    arguments = parse_arguments()

    unit = arguments.unit.strip().upper()
    current_path = Path.cwd()

    if not re.fullmatch(r"WP\d+\.\d+", unit):
        raise RuntimeError(
            "--unit must use the form WPn.m, for example WP1.4."
        )

    git_executable = get_git_executable()
    repo_root = get_repo_root(git_executable, current_path)
    current_branch = get_current_branch(
        git_executable,
        repo_root,
    )

    if current_branch != MAIN_BRANCH:
        raise RuntimeError(
            f"Run this script from the {MAIN_BRANCH} checkout. "
            f"Current branch: {current_branch or '(detached)'}."
        )

    ensure_clean_tree(
        git_executable,
        repo_root,
        "Main working tree",
    )

    ensure_main_matches_remote(
        git_executable,
        repo_root,
    )

    worktree_path = (
        repo_root.parent
        / f"{repo_root.name}-{unit.lower()}"
    )

    if not worktree_path.exists():
        raise RuntimeError(
            f"Expected worktree does not exist: {worktree_path}"
        )

    resolved_target = worktree_path.resolve()  #v1.1
    if resolved_target != worktree_path or resolved_target.parent != repo_root.parent:  #v1.1
        raise RuntimeError("Refusing cleanup of a redirected worktree path.")  #v1.1
    listing = run_command(  #v1.1
        [git_executable, "worktree", "list", "--porcelain", "-z"],  #v1.1
        cwd=repo_root, capture_output=True,  #v1.1
    )  #v1.1
    records = [record.split("\0") for record in listing.stdout.split("\0\0") if record]  #v1.1
    matches = [record for record in records  #v1.1
               if record[0].startswith("worktree ")  #v1.1
               and Path(record[0][9:]) == worktree_path]  #v1.1
    if len(matches) != 1:  #v1.1
        raise RuntimeError("Target is not a registered worktree of this repository.")  #v1.1
    if any(field == "locked" or field.startswith("locked ") for field in matches[0]):  #v1.1
        raise RuntimeError("Worktree is locked; refusing cleanup.")  #v1.1
    if get_repo_root(git_executable, worktree_path) != worktree_path:  #v1.1
        raise RuntimeError("Target is not the root of the expected checkout.")  #v1.1

    branch_result = run_command(
        [
            git_executable,
            "-C",
            str(worktree_path),
            "branch",
            "--show-current",
        ],
        cwd=repo_root,
        capture_output=True,
    )

    branch_name = branch_result.stdout.strip()

    if not branch_name:
        raise RuntimeError(
            "Worktree is detached; refusing automatic cleanup."
        )

    if branch_name == MAIN_BRANCH:
        raise RuntimeError(
            "Worktree is on main; refusing automatic cleanup."
        )

    expected_prefix = f"feat/{unit.lower().replace('.', '-')}-"  #v1.1
    if not re.fullmatch(re.escape(expected_prefix) + r"[a-z0-9]+(?:-[a-z0-9]+)*", branch_name):  #v1.1
        raise RuntimeError("Worktree branch does not match the requested unit's feature branch.")  #v1.1
    if f"branch refs/heads/{branch_name}" not in matches[0]:  #v1.1
        raise RuntimeError("Worktree branch identity changed; refusing cleanup.")  #v1.1

    ensure_clean_tree(
        git_executable,
        worktree_path,
        f"Worktree {worktree_path}",
    )

    ancestor_check = run_command(
        [
            git_executable,
            "merge-base",
            "--is-ancestor",
            branch_name,
            MAIN_BRANCH,
        ],
        cwd=repo_root,
        check=False,
    )

    if ancestor_check.returncode not in (0, 1):  #v1.1
        raise RuntimeError("Git could not verify whether the branch is merged.")  #v1.1

    if ancestor_check.returncode != 0:
        raise RuntimeError(
            f"Branch {branch_name} is not fully merged into "
            f"{MAIN_BRANCH}. Merge it manually first."
        )

    print(f"Removing worktree: {worktree_path}")

    run_command(
        [
            git_executable,
            "worktree",
            "remove",
            str(worktree_path),
        ],
        cwd=repo_root,
    )

    print(f"Deleting merged local branch: {branch_name}")

    try:  #v1.1
        run_command(  #v1.1
            [git_executable, "branch", "-d", branch_name], cwd=repo_root,  #v1.1
        )  #v1.1
    except (RuntimeError, OSError) as exc:  #v1.1
        raise RuntimeError(  #v1.1
            f"Worktree removed, but local branch {branch_name} remains; inspect it manually. {exc}"  #v1.1
        ) from exc  #v1.1

    print("")
    print("Worktree cleanup complete.")
    print(
        "You can now delete the temporary Codex project manually."
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError) as exc:  #v1.1
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
