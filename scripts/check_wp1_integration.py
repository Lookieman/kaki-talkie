# v1.0 | 05-Sep-2026 | Exercise WP1 over real loopback HTTP with optional owned servers.

import argparse  #v1.0
import base64  #v1.0
import io  #v1.0
import socket  #v1.0
import subprocess  #v1.0
import sys  #v1.0
import tempfile  #v1.0
import time  #v1.0
import uuid  #v1.0
import wave  #v1.0
from contextlib import ExitStack  #v1.0
from pathlib import Path  #v1.0

import httpx  #v1.0

from kaki_backend.contracts.responses import TurnResponse  #v1.0
from kaki_backend.main import app  #v1.0

BACKEND = "http://127.0.0.1:8000"  #v1.0
WEB = "http://127.0.0.1:3000"  #v1.0
ROOT = Path(__file__).resolve().parents[1]  #v1.0


def require(condition: bool, message: str) -> None:  #v1.0
    if not condition:  #v1.0
        raise RuntimeError(message)  #v1.0


def check_audio(payload: str | None) -> None:  #v1.0
    require(isinstance(payload, str), "Missing canned audio")  #v1.0
    prefix, encoded = payload.split(",", 1)  #v1.0
    require(prefix == "data:audio/wav;base64", "Unexpected audio payload type")  #v1.0
    data = base64.b64decode(encoded, validate=True)  #v1.0
    with wave.open(io.BytesIO(data), "rb") as audio:  #v1.0
        require(audio.getcomptype() == "NONE", "Canned WAV must be PCM")  #v1.0
        require(audio.getnframes() > audio.getframerate(), "Canned WAV is too short")  #v1.0
        require(any(audio.readframes(audio.getnframes())), "Canned WAV is silent")  #v1.0


def check_stack() -> None:  #v1.0
    with httpx.Client(timeout=15, trust_env=False, follow_redirects=False) as client:  #v1.0
        page = client.get(WEB + "/sim")  #v1.0
        require(page.status_code == 200 and "Hold to talk" in page.text, "Simulator page failed")  #v1.0
        for origin in (BACKEND, WEB):  #v1.0
            health = client.get(origin + "/api/health")  #v1.0
            require(health.status_code == 200, "Health HTTP status failed")  #v1.0
            require(  #v1.0
                health.json() == {"status": "ok", "version": app.version}, "Health shape failed"  #v1.0
            )  #v1.0
            pending = client.get(origin + "/api/device/pending")  #v1.0
            require(pending.status_code == 200 and pending.json() == [], "Pending failed")  #v1.0
        fields = {  #v1.0
            "device_id": "wp14-integration",  #v1.0
            "session_id": str(uuid.uuid4()),  #v1.0
            "turn_id": str(uuid.uuid4()),  #v1.0
        }  #v1.0
        fixture = ROOT / "backend/src/kaki_backend/fixtures/canned_reply.wav"  #v1.0
        response = client.post(  #v1.0
            WEB + "/api/device/turn",  #v1.0
            data=fields,  #v1.0
            files={"audio": ("fixture.wav", fixture.read_bytes(), "audio/wav")},  #v1.0
        )  #v1.0
        require(response.status_code == 200, "Proxied multipart turn failed")  #v1.0
        turn = TurnResponse.model_validate(response.json())  #v1.0
        require(turn.turn_id == fields["turn_id"] and turn.state == "answered", "Turn failed")  #v1.0
        check_audio(turn.reply_audio)  #v1.0
        require("Source: canned test fixture" in turn.slip_text, "Missing fixture source")  #v1.0
        require("05-Sep-2026 (fixture date)" in turn.slip_text, "Missing fixture date")  #v1.0
        require(turn.sources == [], "WP1 must not claim retrieval")  #v1.0
        retry = client.post(  #v1.0
            BACKEND + "/api/device/turn",  #v1.0
            data=fields,  #v1.0
            files={"audio": ("empty.wav", b"", "audio/wav")},  #v1.0
        )  #v1.0
        require(  #v1.0
            retry.status_code == 200 and retry.json() == response.json(), "Retry changed result"  #v1.0
        )  #v1.0
        fields["turn_id"] = str(uuid.uuid4())  #v1.0
        empty = client.post(  #v1.0
            WEB + "/api/device/turn", data=fields, files={"audio": ("empty.wav", b"", "audio/wav")}  #v1.0
        )  #v1.0
        require(empty.status_code == 200, "Empty upload HTTP status failed")  #v1.0
        failed = TurnResponse.model_validate(empty.json())  #v1.0
        require(failed.state == "failed" and bool(failed.reply_text), "Empty upload was not calm")  #v1.0
        check_audio(failed.reply_audio)  #v1.0
        require(failed.reply_audio != turn.reply_audio, "Wrong failure audio")  #v1.0
        del fields["turn_id"]  #v1.0
        invalid = client.post(  #v1.0
            WEB + "/api/device/turn", data=fields, files={"audio": ("empty.wav", b"", "audio/wav")}  #v1.0
        )  #v1.0
        require(invalid.status_code == 422, "Missing turn_id validation failed")  #v1.0
        require(  #v1.0
            any(item["loc"] == ["body", "turn_id"] for item in invalid.json()["detail"]),  #v1.0
            "Missing turn_id validation location failed",  #v1.0
        )  #v1.0
    print("PASS: localhost web/backend, health, pending, audio, receipt, retry and validation")  #v1.0


def stop_owned(process: subprocess.Popen) -> None:  #v1.0
    if process.poll() is None:  #v1.0
        process.terminate()  #v1.0
        try:  #v1.0
            process.wait(timeout=10)  #v1.0
        except subprocess.TimeoutExpired:  #v1.0
            process.kill()  #v1.0
            process.wait(timeout=10)  #v1.0


def main() -> None:  #v1.0
    parser = argparse.ArgumentParser(description="WP1 loopback HTTP integration gate")  #v1.0
    parser.add_argument("--start-services", action="store_true")  #v1.0
    options = parser.parse_args()  #v1.0
    with ExitStack() as stack:  #v1.0
        processes = []  #v1.0
        logs = []  #v1.0
        if options.start_services:  #v1.0
            for port in (8000, 3000):  #v1.0
                with socket.socket() as probe:  #v1.0
                    probe.settimeout(1)  #v1.0
                    require(  #v1.0
                        probe.connect_ex(("127.0.0.1", port)) != 0,  #v1.0
                        f"Port {port} already in use; refusing to touch an existing service",  #v1.0
                    )  #v1.0
            commands = (  #v1.0
                [sys.executable, "-m", "kaki_backend.main"],  #v1.0
                [  #v1.0
                    "node",  #v1.0
                    "apps/web/node_modules/next/dist/bin/next",  #v1.0
                    "start",  #v1.0
                    "apps/web",  #v1.0
                    "--hostname",  #v1.0
                    "127.0.0.1",  #v1.0
                    "--port",  #v1.0
                    "3000",  #v1.0
                ],  #v1.0
            )  #v1.0
            for command in commands:  #v1.0
                log = stack.enter_context(tempfile.TemporaryFile(mode="w+", encoding="utf-8"))  #v1.0
                process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=log)  #v1.0
                stack.callback(stop_owned, process)  #v1.0
                processes.append(process)  #v1.0
                logs.append(log)  #v1.0
            deadline = time.monotonic() + 45  #v1.0
            try:  #v1.0
                with httpx.Client(timeout=1, trust_env=False) as client:  #v1.0
                    while True:  #v1.0
                        require(  #v1.0
                            all(process.poll() is None for process in processes),  #v1.0
                            "A local server exited before readiness",  #v1.0
                        )  #v1.0
                        try:  #v1.0
                            if all(  #v1.0
                                client.get(url).status_code == 200  #v1.0
                                for url in (BACKEND + "/api/health", WEB + "/sim")  #v1.0
                            ):  #v1.0
                                break  #v1.0
                        except httpx.TransportError:  #v1.0
                            pass  #v1.0
                        require(time.monotonic() < deadline, "Server readiness timed out")  #v1.0
                        time.sleep(0.25)  #v1.0
                check_stack()  #v1.0
            except Exception:  #v1.0
                for log in logs:  #v1.0
                    log.seek(0)  #v1.0
                    print(log.read(), file=sys.stderr)  #v1.0
                raise  #v1.0
        else:  #v1.0
            check_stack()  #v1.0


if __name__ == "__main__":  #v1.0
    main()  #v1.0
