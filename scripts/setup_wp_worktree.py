# v1.0 | 05-Sep-2026 | Create an isolated WP worktree and local development environment safely.

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


MAIN_BRANCH = "main"
REMOTE_NAME = "origin"
DEFAULT_SLUG = "implementation"


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


def get_current_branch(git_executable: str, repo_root: Path) -> str:
    result = run_command(
        [git_executable, "branch", "--show-current"],
        cwd=repo_root,
        capture_output=True,
    )

    return result.stdout.strip()


def ensure_clean_main(git_executable: str, repo_root: Path) -> None:
    result = run_command(
        [git_executable, "status", "--porcelain"],
        cwd=repo_root,
        capture_output=True,
    )

    if result.stdout.strip():
        raise RuntimeError(
            "Main working tree is not clean. "
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
        raise RuntimeError("Could not determine local/remote main status.")

    local_only = int(counts[0])
    remote_only = int(counts[1])

    if local_only != 0 or remote_only != 0:
        raise RuntimeError(
            "Local main and origin/main are not identical. "
            f"Local-only commits: {local_only}; "
            f"remote-only commits: {remote_only}. "
            "Synchronise main manually first."
        )


def normalise_slug(slug: str) -> str:
    normalised_slug = slug.strip().lower()
    normalised_slug = re.sub(r"[^a-z0-9]+", "-", normalised_slug)

    return normalised_slug.strip("-")


def get_venv_python(venv_path: Path) -> Path:
    if sys.platform == "win32":
        return venv_path / "Scripts" / "python.exe"

    return venv_path / "bin" / "python"


def create_python_environment(worktree_path: Path) -> None:
    backend_pyproject = worktree_path / "backend" / "pyproject.toml"

    if not backend_pyproject.exists():
        print("No backend/pyproject.toml found; skipping Python setup.")
        return

    venv_path = worktree_path / ".venv"
    base_python = getattr(sys, "_base_executable", sys.executable)

    print(f"Creating virtual environment: {venv_path}")

    run_command(
        [base_python, "-m", "venv", str(venv_path)],
        cwd=worktree_path,
    )

    venv_python = get_venv_python(venv_path)

    print("Installing backend test dependencies.")

    run_command(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "-e",
            "backend[test]",
        ],
        cwd=worktree_path,
    )


def install_web_dependencies(worktree_path: Path) -> None:
    web_path = worktree_path / "apps" / "web"
    package_json = web_path / "package.json"

    if not package_json.exists():
        print("No apps/web/package.json found; skipping web setup.")
        return

    npm_executable = shutil.which("npm")

    if not npm_executable:
        raise RuntimeError(
            "apps/web/package.json exists but npm was not found on PATH."
        )

    package_lock = web_path / "package-lock.json"

    if package_lock.exists():
        npm_command = "ci"
    else:
        npm_command = "install"

    print(f"Installing web dependencies with npm {npm_command}.")

    run_command(
        [npm_executable, npm_command],
        cwd=web_path,
    )


def run_baseline_tests(worktree_path: Path) -> None:
    venv_python = get_venv_python(worktree_path / ".venv")
    backend_tests = worktree_path / "backend" / "tests" / "contract"

    if venv_python.exists() and backend_tests.exists():
        print("Running backend contract baseline tests.")

        run_command(
            [
                str(venv_python),
                "-m",
                "unittest",
                "discover",
                "-s",
                "backend/tests/contract",
            ],
            cwd=worktree_path,
        )

    web_path = worktree_path / "apps" / "web"
    package_json = web_path / "package.json"
    npm_executable = shutil.which("npm")

    if package_json.exists() and npm_executable:
        print("Running web baseline tests.")

        run_command(
            [npm_executable, "test"],
            cwd=web_path,
        )

        run_command(
            [npm_executable, "run", "lint"],
            cwd=web_path,
        )

        run_command(
            [npm_executable, "run", "build"],
            cwd=web_path,
        )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create an isolated KaKi-Talkie worktree "
            "for one implementation unit."
        )
    )

    parser.add_argument(
        "--unit",
        required=True,
        help="Implementation unit, for example WP1.4.",
    )

    parser.add_argument(
        "--slug",
        default=DEFAULT_SLUG,
        help="Short branch description, for example deployment-wiring.",
    )

    parser.add_argument(
        "--run-baseline",
        action="store_true",
        help="Run backend and web baseline checks after setup.",
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    unit = arguments.unit.strip().upper()
    slug = normalise_slug(arguments.slug)
    current_path = Path.cwd()

    if not re.fullmatch(r"WP\d+\.\d+", unit):
        raise RuntimeError(
            "--unit must use the form WPn.m, for example WP1.4."
        )

    if not slug:
        raise RuntimeError("--slug cannot be empty.")

    git_executable = get_git_executable()
    repo_root = get_repo_root(git_executable, current_path)
    current_branch = get_current_branch(git_executable, repo_root)

    if current_branch != MAIN_BRANCH:
        raise RuntimeError(
            f"Run this script from the {MAIN_BRANCH} checkout. "
            f"Current branch: {current_branch or '(detached)'}."
        )

    ensure_clean_main(git_executable, repo_root)
    ensure_main_matches_remote(git_executable, repo_root)

    unit_path = unit.lower()
    unit_branch = unit.lower().replace(".", "-")

    worktree_path = repo_root.parent / f"{repo_root.name}-{unit_path}"
    branch_name = f"feat/{unit_branch}-{slug}"

    if worktree_path.exists():
        raise RuntimeError(
            f"Worktree path already exists: {worktree_path}"
        )

    branch_check = run_command(
        [
            git_executable,
            "show-ref",
            "--verify",
            "--quiet",
            f"refs/heads/{branch_name}",
        ],
        cwd=repo_root,
        check=False,
    )

    if branch_check.returncode == 0:
        raise RuntimeError(
            f"Local branch already exists: {branch_name}"
        )

    print(f"Creating worktree: {worktree_path}")
    print(f"Creating branch  : {branch_name}")

    run_command(
        [
            git_executable,
            "worktree",
            "add",
            "-b",
            branch_name,
            str(worktree_path),
            MAIN_BRANCH,
        ],
        cwd=repo_root,
    )

    create_python_environment(worktree_path)
    install_web_dependencies(worktree_path)

    if arguments.run_baseline:
        run_baseline_tests(worktree_path)

    print("")
    print("Worktree setup complete.")
    print(f"Path   : {worktree_path}")
    print(f"Branch : {branch_name}")

    if sys.platform == "win32":
        print(
            "Activate: "
            f"{worktree_path}\\.venv\\Scripts\\Activate.ps1"
        )

    print(
        "Create a temporary Codex project pointing only "
        "to this worktree."
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)