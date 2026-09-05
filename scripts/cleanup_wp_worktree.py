# v1.0 | 05-Sep-2026 | Remove a merged and pushed WP worktree and its local branch safely.

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
    git_executable = shutil.which("git")

    if not git_executable:
        raise RuntimeError("Git was not found on PATH.")

    return git_executable


def get_repo_root(git_executable: str, start_path: Path) -> Path:
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

    if len(counts) != 2:
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
    parser = argparse.ArgumentParser(
        description=(
            "Safely remove a merged KaKi-Talkie "
            "implementation-unit worktree."
        )
    )

    parser.add_argument(
        "--unit",
        required=True,
        help="Implementation unit, for example WP1.4.",
    )

    return parser.parse_args()


def main() -> int:
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

    run_command(
        [
            git_executable,
            "branch",
            "-d",
            branch_name,
        ],
        cwd=repo_root,
    )

    run_command(
        [
            git_executable,
            "worktree",
            "prune",
        ],
        cwd=repo_root,
    )

    print("")
    print("Worktree cleanup complete.")
    print(
        "You can now delete the temporary Codex project manually."
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)