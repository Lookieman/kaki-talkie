# v1.0 | 12-Sep-2026 | Make the deterministic suites hermetic against ambient KAKI_* exports.
"""Give the deterministic test suites a canned environment of their own.

`kaki_backend.config` selects every adapter from the process environment, and
`kaki_backend.main` builds the application at import time. A validation shell
that exported `KAKI_STT_MODE=whisper`, `KAKI_LLM_MODE=qwen`,
`KAKI_TTS_MODE=say` or `KAKI_RETRIEVAL_MODE=rag` therefore leaked those
switches into Tier A runs, which then called live Whisper, MLX-LM, `say` and
Chroma: eight false contract failures with the stack down, a different set
with it up. The `StarletteDeprecationWarning` printed by those runs is
cosmetic and was never the cause.

Two entry points, because the two leaks happen at different moments:

- `canned_backend()` sanitises the environment and only then imports
  `kaki_backend.main`, returning the module. Contract tests take `app` from
  it instead of importing it directly, so the application is always built
  from canned settings no matter how the caller orders its imports.
- `CannedEnvironment` is a `unittest` mixin for tests that read the
  environment while running. It snapshots, sanitises and restores around
  every test method.

This module sits at the repository root so that all four suites can import
it: `python -m unittest` puts the working directory first on `sys.path`, and
every documented suite command runs from the checkout root (runbook 8.2
WP3.4 Test 7). An `ImportError` here means the command ran from elsewhere.
"""

import atexit
import os
import shutil
import tempfile
from types import ModuleType

# Every switch `kaki_backend.config` reads, pinned to the deterministic
# adapters. Canned mode needs no model service, no network and no data root.
CANNED_ENVIRONMENT = {
    "KAKI_STT_MODE": "canned",
    "KAKI_LLM_MODE": "canned",
    "KAKI_TTS_MODE": "canned",
    "KAKI_RETRIEVAL_MODE": "canned",
    "KAKI_QUERY_NORMALISE": "on",
}

_disposable_root: str | None = None


def _data_root() -> str:
    """Return a process-local data root, created once and removed at exit.

    Canned adapters never write to it. It exists so that a suite resolving
    `KAKI_DATA_ROOT` cannot reach the owner's real runtime data.
    """
    global _disposable_root
    if _disposable_root is None:
        _disposable_root = tempfile.mkdtemp(prefix="kaki-test-data-")
        atexit.register(shutil.rmtree, _disposable_root, ignore_errors=True)
    return _disposable_root


def canned_environment() -> dict[str, str]:
    """Return the canned switches together with the disposable data root."""
    return {**CANNED_ENVIRONMENT, "KAKI_DATA_ROOT": _data_root()}


def install_canned_environment() -> None:
    """Replace every `KAKI_*` export in this process with the canned settings.

    Removes unknown `KAKI_*` names too, so a switch added later cannot leak
    into a suite that predates it. Idempotent; restores nothing, because the
    calling process exists only to run tests.
    """
    for name in [name for name in os.environ if name.startswith("KAKI_")]:
        del os.environ[name]
    os.environ.update(canned_environment())


def canned_backend() -> ModuleType:
    """Sanitise the environment, then import and return `kaki_backend.main`.

    The import is deliberately inside this function: the application is
    constructed during it, so the sanitising above must already have run.
    """
    install_canned_environment()
    from kaki_backend import main

    return main


def _restore(snapshot: dict[str, str]) -> None:
    """Replace the live environment with an earlier snapshot of it."""
    os.environ.clear()
    os.environ.update(snapshot)


class CannedEnvironment:
    """Mixin giving each test a canned `KAKI_*` environment, then restoring it.

    Mix in before `unittest.TestCase`. A subclass with its own `setUp` must
    call `super().setUp()` first so the sanitising happens before its own
    fixtures are built.
    """

    def setUp(self) -> None:
        """Snapshot and sanitise the environment; registered cleanup restores it."""
        self.addCleanup(_restore, dict(os.environ))
        install_canned_environment()
        super().setUp()
