# v1.2 | 12-Sep-2026 | Retry cold readiness probes quickly; load HF_TOKEN from .env.
# v1.1 | 11-Sep-2026 | Start the grounded stack: retrieval mode export and readiness wait.
# v1.0 | 09-Sep-2026 | Provide the WP2.4 owner helper to start, check and stop the Mac stack.
"""Start, check or stop the local KaKi-Talkie development stack on the Mac.

`up` starts whisper-server, the MLX-LM server (thinking disabled) and the
FastAPI backend, in that order, detached from the terminal, waiting for each
service's health endpoint before starting the next. `status` reports each
service's recorded process and health. `down` stops, in reverse order, only
the processes this helper started, identified by its own pidfiles and a
command-line match; it never performs broad process kills. The Next.js
simulator is not managed here (runbook 7.4.1; start it per setup.md 14).

Side effects: `up` spawns three long-running local processes, writes logs
under `$KAKI_DATA_ROOT/logs` and pidfiles under `$KAKI_DATA_ROOT/run`, and
exports real-mode backend settings (whisper/qwen/say and grounded retrieval;
export `KAKI_RETRIEVAL_MODE=canned` first for the WP2 configuration) unless
already set in the environment. With retrieval grounded, backend readiness
also requires the health `retrieval_ready` flag, whose first probe loads the
embedding model. `down` signals those recorded processes and removes their
pidfiles. Requires an absolute `KAKI_DATA_ROOT`. Paths follow setup.md and
may be overridden: `KAKI_WHISPER_SERVER`, `KAKI_WHISPER_MODEL`,
`KAKI_LLM_PYTHON`, `HF_HOME`. Exit status is zero on success; 2 indicates a
usage or configuration error.
"""

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv  #v1.2

# `HF_TOKEN` lives in the untracked project-root .env. Load it before any
# service starts so the spawned backend and MLX-LM inherit it; a real export
# always wins, and a missing .env is a silent no-op.
load_dotenv()  #v1.2

READINESS_POLL_SECONDS = 2.0
STOP_GRACE_SECONDS = 20.0


@dataclass(frozen=True)
class Service:
    """Describe one managed local service: how to start, verify and identify it."""

    name: str
    port: int
    health_url: str
    command: tuple[str, ...]
    marker: str
    readiness_deadline_seconds: float
    extra_environment: tuple[tuple[str, str], ...] = ()
    required_health_flags: tuple[str, ...] = ()  #v1.1


def build_services(environment: dict[str, str]) -> list[Service]:
    """Return the three managed services in start order using setup.md defaults."""
    home = Path.home()
    whisper_server = environment.get(
        "KAKI_WHISPER_SERVER", str(home / "src/whisper.cpp/build/bin/whisper-server")
    )
    whisper_model = environment.get(
        "KAKI_WHISPER_MODEL", str(home / "models/whisper/ggml-large-v3-turbo.bin")
    )
    llm_python = environment.get("KAKI_LLM_PYTHON", str(home / ".venvs/kaki-llm/bin/python"))
    hf_home = environment.get("HF_HOME", str(home / "models/huggingface"))
    backend_settings = (
        ("KAKI_STT_MODE", "whisper"),
        ("KAKI_WHISPER_URL", "http://127.0.0.1:8081"),
        ("KAKI_LLM_MODE", "qwen"),
        ("KAKI_LLM_URL", "http://127.0.0.1:8082"),
        ("KAKI_TTS_MODE", "say"),
        ("KAKI_RETRIEVAL_MODE", "rag"),  #v1.1
        ("HF_HOME", hf_home),  #v1.1
    )
    # An explicit KAKI_RETRIEVAL_MODE=canned export selects the WP2 configuration.
    retrieval_grounded = environment.get("KAKI_RETRIEVAL_MODE", "rag") == "rag"  #v1.1
    return [
        Service(
            name="whisper", port=8081, health_url="http://127.0.0.1:8081/health",
            command=(
                whisper_server, "--host", "127.0.0.1", "--port", "8081",
                "-m", whisper_model, "-l", "auto",
            ),
            marker="whisper-server", readiness_deadline_seconds=180,
        ),
        Service(
            name="llm", port=8082, health_url="http://127.0.0.1:8082/health",
            command=(
                llm_python, "-m", "mlx_lm", "server",
                "--model", "mlx-community/Qwen3-8B-4bit",
                "--host", "127.0.0.1", "--port", "8082",
                "--chat-template-args", '{"enable_thinking":false}',
            ),
            marker="mlx_lm", readiness_deadline_seconds=300,
            extra_environment=(("HF_HOME", hf_home),),
        ),
        Service(
            name="backend", port=8000, health_url="http://127.0.0.1:8000/api/health",
            command=(sys.executable, "-m", "kaki_backend.main"),
            # First grounded readiness also loads the embedding model (~1.2 GB).
            marker="kaki_backend",  #v1.1
            readiness_deadline_seconds=180 if retrieval_grounded else 60,  #v1.1
            extra_environment=backend_settings,
            required_health_flags=(  #v1.1
                ("retrieval_ready",) if retrieval_grounded else ()
            ),
        ),
    ]


def port_is_free(port: int) -> bool:
    """Report whether nothing accepts connections on the loopback port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def service_healthy(service: Service) -> bool:
    """Report whether health answers 200 and its required readiness flags are true.

    The grounded backend warms the embedding model inside its readiness
    probe. A cold load outlasts any sensible per-probe wait, so the probe
    gives up quickly and the caller retries: the model is either resident
    and answers promptly, or still loading and a later poll will catch it.
    Abandoned probes cost nothing because the adapter serialises model
    loading onto one worker thread.
    """  #v1.2
    timeout = 10.0 if service.required_health_flags else 2.0  #v1.2
    try:
        with httpx.Client(timeout=timeout, trust_env=False, follow_redirects=False) as client:  #v1.1
            response = client.get(service.health_url)
            if response.status_code != 200:
                return False
            if not service.required_health_flags:  #v1.1
                return True
            payload = response.json()  #v1.1
            return all(payload.get(flag) is True for flag in service.required_health_flags)
    except (httpx.HTTPError, ValueError):  #v1.1
        return False


def pidfile_path(run_directory: Path, service: Service) -> Path:
    """Return the pidfile location for one service."""
    return run_directory / f"{service.name}.pid.json"


def read_pidfile(path: Path) -> dict[str, object] | None:
    """Return the recorded process details, or None when absent or unreadable."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or not isinstance(record.get("pid"), int):
        return None
    return record


def recorded_process_alive(record: dict[str, object], marker: str) -> bool:
    """Report whether the recorded pid is alive and still runs the expected command."""
    pid = int(record["pid"])
    try:
        listing = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return listing.returncode == 0 and marker in listing.stdout


def start_service(service: Service, run_directory: Path, log_directory: Path) -> bool:
    """Spawn one detached service and record its pidfile; report success."""
    pidfile = pidfile_path(run_directory, service)
    if pidfile.exists():
        print(f"FAIL: {pidfile} exists; run 'down' first or remove a stale record.",
              file=sys.stderr)
        return False
    if not port_is_free(service.port):
        print(f"FAIL: port {service.port} is already in use; not touching the existing "
              f"process (runbook 7.2.2 Test 1).", file=sys.stderr)
        return False
    environment = {**os.environ}
    for name, value in service.extra_environment:
        environment.setdefault(name, value)
    log_path = log_directory / f"{service.name}.log"
    try:
        with log_path.open("ab") as log_file:
            process = subprocess.Popen(
                service.command, stdout=log_file, stderr=log_file,
                stdin=subprocess.DEVNULL, env=environment, start_new_session=True,
            )
    except OSError as error:
        print(f"FAIL: cannot start {service.name}: {error}", file=sys.stderr)
        return False
    pidfile.write_text(
        json.dumps({"pid": process.pid, "marker": service.marker}), encoding="utf-8"
    )
    print(f"started {service.name} (pid {process.pid}); log: {log_path}")
    return True


def wait_until_ready(service: Service) -> bool:
    """Poll the health endpoint until ready or the service deadline passes."""
    deadline = time.monotonic() + service.readiness_deadline_seconds
    while time.monotonic() < deadline:
        if service_healthy(service):
            print(f"{service.name} is ready ({service.health_url})")
            return True
        time.sleep(READINESS_POLL_SECONDS)
    print(f"FAIL: {service.name} did not become ready within "
          f"{service.readiness_deadline_seconds:g}s; see its log.", file=sys.stderr)
    return False


def stop_service(service: Service, run_directory: Path) -> bool:
    """Stop only the recorded process for one service; report success."""
    pidfile = pidfile_path(run_directory, service)
    record = read_pidfile(pidfile)
    if record is None:
        if pidfile.exists():
            print(f"FAIL: {pidfile} is unreadable; inspect it manually.", file=sys.stderr)
            return False
        print(f"{service.name}: nothing recorded to stop")
        return True
    if not recorded_process_alive(record, service.marker):
        print(f"{service.name}: recorded process already gone; removing pidfile")
        pidfile.unlink(missing_ok=True)
        return True
    pid = int(record["pid"])
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + STOP_GRACE_SECONDS
    while time.monotonic() < deadline:
        if not recorded_process_alive(record, service.marker):
            break
        time.sleep(0.5)
    else:
        print(f"WARN: {service.name} ignored SIGTERM; sending SIGKILL to pid {pid} only.",
              file=sys.stderr)
        os.kill(pid, signal.SIGKILL)
    pidfile.unlink(missing_ok=True)
    print(f"stopped {service.name} (pid {pid})")
    return True


def command_up(services: list[Service], run_directory: Path, log_directory: Path) -> int:
    """Start every service in order; on failure stop what this invocation started."""
    started: list[Service] = []
    for service in services:
        if not start_service(service, run_directory, log_directory):
            break
        started.append(service)
        if not wait_until_ready(service):
            break
    else:
        print("PASS: full stack is up; simulator is not managed here (setup.md 14).")
        return 0
    for service in reversed(started):
        stop_service(service, run_directory)
    return 1


def command_down(services: list[Service], run_directory: Path) -> int:
    """Stop recorded services in reverse start order."""
    succeeded = all([stop_service(service, run_directory) for service in reversed(services)])
    return 0 if succeeded else 1


def command_status(services: list[Service], run_directory: Path) -> int:
    """Print recorded process and health state per service; zero only when all healthy."""
    all_healthy = True
    for service in services:
        record = read_pidfile(pidfile_path(run_directory, service))
        recorded = record is not None and recorded_process_alive(record, service.marker)
        healthy = service_healthy(service)
        all_healthy = all_healthy and healthy
        print(json.dumps({
            "service": service.name, "port": service.port,
            "recorded_process": recorded, "healthy": healthy,
        }))
    print("PASS: all services healthy." if all_healthy else "FAIL: not all services healthy.",
          file=sys.stderr)
    return 0 if all_healthy else 1


def build_parser() -> argparse.ArgumentParser:
    """Describe the up/down/status actions."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "action", choices=["up", "down", "status"],
        help="up: start and await the stack; down: stop recorded processes; "
        "status: report health",
    )
    parser.add_argument(
        "--only", choices=["whisper", "llm", "backend"],
        help="Act on a single service, e.g. for the runbook 7.4.2 degraded-readiness test",
    )
    return parser


def main() -> int:
    """Dispatch the requested stack action under KAKI_DATA_ROOT."""
    args = build_parser().parse_args()
    data_root = Path(os.environ.get("KAKI_DATA_ROOT", ""))
    if not data_root.is_absolute():
        print("FAIL: export an absolute KAKI_DATA_ROOT first (runbook 7.4.1).", file=sys.stderr)
        return 2
    run_directory = data_root / "run"
    log_directory = data_root / "logs"
    run_directory.mkdir(parents=True, exist_ok=True)
    log_directory.mkdir(parents=True, exist_ok=True)
    services = build_services(dict(os.environ))
    if args.only is not None:
        services = [service for service in services if service.name == args.only]
    if args.action == "up":
        return command_up(services, run_directory, log_directory)
    if args.action == "down":
        return command_down(services, run_directory)
    return command_status(services, run_directory)


if __name__ == "__main__":
    raise SystemExit(main())
