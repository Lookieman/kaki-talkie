# v1.1 | 06-Sep-2026 | Document CLI use and strengthen validation and failure safety.
# v1.0 | 05-Sep-2026 | Create an isolated WP worktree and local development environment safely.

"""Create a sibling implementation-unit worktree from clean, synchronised main.

Run on the Windows development desktop before implementation. Fetches origin,
creates feat/wpN-M-slug and a sibling checkout, installs local Python/npm
dependencies (which may use the network and run package installation scripts),
and optionally runs baseline checks. Failed setup is retained for manual recovery.
Never commits, merges or pushes. See docs/04-prototype/wp-validation-runbook.md.
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
DEFAULT_SLUG = "implementation"


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


def get_current_branch(git_executable: str, repo_root: Path) -> str:
    """Return the checked-out branch name, or an empty string for detached HEAD."""  #v1.1
    result = run_command(
        [git_executable, "branch", "--show-current"],
        cwd=repo_root,
        capture_output=True,
    )

    return result.stdout.strip()


def ensure_clean_main(git_executable: str, repo_root: Path) -> None:
    """Refuse setup when main contains tracked changes or untracked files."""  #v1.1
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
    """Convert a description to a lowercase, hyphen-separated branch suffix."""  #v1.1
    normalised_slug = slug.strip().lower()
    normalised_slug = re.sub(r"[^a-z0-9]+", "-", normalised_slug)

    return normalised_slug.strip("-")


def get_venv_python(venv_path: Path) -> Path:
    """Return the platform-specific interpreter path inside a local environment."""  #v1.1
    if sys.platform == "win32":
        return venv_path / "Scripts" / "python.exe"

    return venv_path / "bin" / "python"


def create_python_environment(worktree_path: Path) -> None:
    """Create a worktree-local venv and install backend[test], when present."""  #v1.1
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
    """Install web dependencies using npm ci with a lockfile, else npm install."""  #v1.1
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
    """Run available backend contract and web test/lint/build checks; fail on errors."""  #v1.1
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
    """Parse CLI options; help exits zero and invalid usage exits non-zero."""  #v1.1
    parser = argparse.ArgumentParser(
        description=(
            "Create an isolated KaKi-Talkie worktree "
            "for one implementation unit."
        ),  #v1.1
        epilog=(  #v1.1
            "Requires Git, clean main matching origin/main, Python with venv and npm when web exists. Creates <repo>-wpN.M beside the repository and feat/wpN-M-<slug>; installs dependencies and may run package scripts. Fetch and installation may access the network. Partial setup is retained on failure. "  #v1.1
            "No automatic commit, merge or push. "  #v1.1
            "Example: python scripts/setup_wp_worktree.py --unit WP2.1 --slug audio-normalisation --run-baseline. "  #v1.1
            "Guide: docs/04-prototype/wp-validation-runbook.md"  #v1.1
        ),  #v1.1
    )

    parser.add_argument(
        "--unit",
        required=True,
        help="Required unit in WPn.m form (case-insensitive), for example WP2.1.",  #v1.1
    )

    parser.add_argument(
        "--slug",
        default=DEFAULT_SLUG,
        help="Branch suffix; normalised to lowercase hyphenated text (default: implementation).",  #v1.1
    )

    parser.add_argument(
        "--run-baseline",
        action="store_true",
        help="After installation, run available backend contract tests and web test/lint/build (default: off).",  #v1.1
    )

    return parser.parse_args()


def main() -> int:
    """Validate prerequisites and perform the requested operation; return zero on success."""  #v1.1
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

    if worktree_path.exists() or worktree_path.is_symlink():  #v1.1
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

    if branch_check.returncode != 1:  #v1.1
        raise RuntimeError("Could not reliably check whether the local branch exists.")  #v1.1

    if (repo_root / "apps/web/package.json").exists() and not shutil.which("npm"):  #v1.1
        raise RuntimeError("Web setup requires npm on PATH; install it before setup.")  #v1.1
    if (repo_root / "backend/pyproject.toml").exists():  #v1.1
        base_python = getattr(sys, "_base_executable", sys.executable)  #v1.1
        run_command([base_python, "-c", "import venv, ensurepip"], cwd=repo_root)  #v1.1

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

    try:  #v1.1
        create_python_environment(worktree_path)  #v1.1
        install_web_dependencies(worktree_path)  #v1.1

        if arguments.run_baseline:  #v1.1
            run_baseline_tests(worktree_path)  #v1.1
    except (RuntimeError, OSError) as exc:  #v1.1
        raise RuntimeError(  #v1.1
            f"Setup incomplete at {worktree_path} on {branch_name}; retained for manual recovery. {exc}"  #v1.1
        ) from exc  #v1.1

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
    except (RuntimeError, OSError) as exc:  #v1.1
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
