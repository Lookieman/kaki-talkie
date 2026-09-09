# v1.0 | 09-Sep-2026 | Generate bounded concise replies through the local MLX-LM server.
"""Use the local MLX-LM chat completions API behind the backend's LLM port.

The model stays in its own process (`mlx_lm.server` on loopback port 8082).
This adapter sends the recognised transcript with a fixed concise-answer
system prompt, never follows redirects or environment proxies, and never
logs transcripts, reply text or upstream error bodies. Readiness requires
the approved model to be resident, not merely a listening socket.
"""

import ipaddress
import json
import math
from time import monotonic
from urllib.parse import urlsplit

import httpx

from kaki_backend.contracts.ports import LlmError

MAX_RESPONSE_BYTES = 256 * 1024
MAX_TRANSCRIPT_CHARS = 16384
MAX_COMPLETION_TOKENS = 400
READINESS_TIMEOUT_SECONDS = 2.0

# TODO(WP-DSPy): migrate this literal prompt to a DSPy signature/module when the
# execution plan reaches the DSPy unit. Authorised as a WP2.3-only temporary
# constant; do not copy this pattern into later units.
SYSTEM_PROMPT = (
    "You are KaKi-Talkie, a calm community helper kiosk for elderly users in "
    "Singapore. Answer the user's request in plain spoken English in 60 words "
    "or fewer. Use short complete sentences. Do not use lists, headings, "
    "markdown or emojis. If you are unsure, say so briefly and suggest asking "
    "a staff member."
)


class QwenLlm:
    """Call a loopback-only MLX-LM server with bounded I/O and sanitised failures."""

    def __init__(
        self, url: str = "http://127.0.0.1:8082", *, model: str, timeout_seconds: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Validate the local endpoint; transport injection supports deterministic tests."""
        try:
            parsed = urlsplit(url)
            valid = (
                parsed.scheme == "http" and parsed.port is not None
                and ipaddress.ip_address(parsed.hostname or "").is_loopback
                and parsed.username is None and parsed.password is None
                and not parsed.path and not parsed.query and not parsed.fragment
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("LLM URL must be a plain HTTP literal loopback address and port.")
        if not model or not model.strip():
            raise ValueError("LLM model identifier must be a non-empty string.")
        if not math.isfinite(timeout_seconds) or not 0.1 <= timeout_seconds <= 300:
            raise ValueError("LLM timeout must be between 0.1 and 300 seconds.")
        self._url = url
        self._model = model.strip()
        self._timeout = timeout_seconds
        self._transport = transport

    def ready(self) -> bool:
        """Return true only when the approved model is resident; never trigger a load."""
        try:
            payload = self._request("GET", "/v1/models", READINESS_TIMEOUT_SECONDS)
        except LlmError:
            return False
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            return False
        return any(
            isinstance(entry, dict) and entry.get("id") == self._model
            for entry in payload["data"]
        )

    def generate(self, transcript: str) -> str:
        """Return a concise sanitised reply for the transcript or raise LlmError."""
        if not transcript.strip() or len(transcript) > MAX_TRANSCRIPT_CHARS:
            raise LlmError("invalid_response")
        payload = self._request(
            "POST", "/v1/chat/completions", self._timeout,
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": transcript},
                ],
                "max_tokens": MAX_COMPLETION_TOKENS,
                "stream": False,
            },
        )
        return _extract_reply(payload)

    def _request(self, method: str, path: str, timeout: float, **kwargs: object) -> object:
        """Cap response bytes and network waits, closing request resources on every path."""
        try:
            started = monotonic()
            with httpx.Client(
                timeout=httpx.Timeout(timeout, connect=min(2.0, timeout)),
                trust_env=False, follow_redirects=False, transport=self._transport,
                headers={"Accept-Encoding": "identity"},
            ) as client:
                with client.stream(method, self._url + path, **kwargs) as response:
                    if response.status_code != 200:
                        raise LlmError("unavailable")
                    if response.headers.get("content-encoding", "identity") != "identity":
                        raise LlmError("invalid_response")
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        if monotonic() - started > timeout:
                            raise LlmError("timeout")
                        if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise LlmError("invalid_response")
                        body.extend(chunk)
                    return json.loads(body)
        except httpx.TimeoutException:
            raise LlmError("timeout") from None
        except (httpx.HTTPError, OSError):
            raise LlmError("unavailable") from None
        except (ValueError, UnicodeError):
            raise LlmError("invalid_response") from None


def _extract_reply(payload: object) -> str:
    """Read the first chat choice, strip any think block, and reject empty output.

    The server is started with thinking disabled; stripping here is defence in
    depth so a configuration slip cannot leak deliberation text to the kiosk.
    """
    if not isinstance(payload, dict) or "error" in payload:
        raise LlmError("invalid_response")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise LlmError("invalid_response")
    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise LlmError("invalid_response")
    text = message["content"]
    if "<think>" in text:
        opening = text.index("<think>")
        closing = text.find("</think>", opening)
        if closing < 0:
            raise LlmError("invalid_response")
        text = text[:opening] + text[closing + len("</think>"):]
    if "<think>" in text or "</think>" in text:
        raise LlmError("invalid_response")
    if not text.strip():
        raise LlmError("empty_reply")
    return text.strip()
