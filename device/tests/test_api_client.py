# v1.0 | 16-Sep-2026 | WP6.1 backend client: contract fields, audio decoding, safe failures.
"""Exercise the device's HTTP client with an injected transport; no backend runs.

Three properties matter here. The request carries the contract's multipart
fields including `turn_id`, the nine-field response parses without
interpretation, and every failure becomes a safe code rather than an exception
carrying a payload.

Reply audio gets its own class of tests because the contract types it
`str | None` with no format pinned: the client accepts the WAV data URL every
producer emits and refuses to guess at anything else.
"""

import io
import unittest
import wave
from base64 import b64encode

import httpx

from kaki_device.api_client import (
    AUDIO_DATA_URL_PREFIX,
    HEALTH_PATH,
    PENDING_PATH,
    TURN_PATH,
    ApiError,
    BackendClient,
    UnplayableAudio,
    decode_reply_audio,
)


def wav_bytes(frames: int = 400, channels: int = 1, framerate: int = 22050) -> bytes:
    """Return a small valid PCM WAV payload."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setnchannels(channels)
        recording.setsampwidth(2)
        recording.setframerate(framerate)
        recording.writeframes(b"\x01\x00" * frames * channels)
    return buffer.getvalue()


def data_url(audio: bytes) -> str:
    """Encode WAV bytes exactly as the backend's producers do."""
    return AUDIO_DATA_URL_PREFIX + b64encode(audio).decode("ascii")


def turn_payload(**overrides) -> dict:
    """Return a complete nine-field response body."""
    payload = {
        "turn_id": "turn-1",
        "reply_audio": data_url(wav_bytes()),
        "reply_text": "Open the SMS link from CDC.",
        "display_text": "Open the SMS link from CDC.",
        "slip_text": "KAKI-TALKIE HELP\nOpen the SMS link.",
        "language": "en",
        "state": "answered",
        "case_id": None,
        "sources": [{"source_url": "https://vouchers.cdc.gov.sg/", "page_title": "CDC"}],
    }
    payload.update(overrides)
    return payload


def client_for(handler) -> BackendClient:
    """Build a client whose HTTP layer is served by `handler`."""
    return BackendClient(
        "http://127.0.0.1:8000", timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )


class TurnRequestTests(unittest.TestCase):
    """The request matches the WP1 device contract."""

    def test_multipart_carries_the_contract_fields_including_turn_id(self):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            seen["method"] = request.method
            seen["body"] = request.content
            return httpx.Response(200, json=turn_payload())

        client_for(handler).submit_turn(
            device_id="kaki-pi-01", session_id="session-9", turn_id="turn-1",
            audio=wav_bytes(),
        )
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(seen["url"], "http://127.0.0.1:8000" + TURN_PATH)
        body = seen["body"]
        for field in (b"device_id", b"session_id", b"turn_id"):
            self.assertIn(field, body)
        for value in (b"kaki-pi-01", b"session-9", b"turn-1"):
            self.assertIn(value, body)
        self.assertIn(b"RIFF", body)

    def test_response_parses_into_the_nine_contract_fields(self):
        result = client_for(
            lambda request: httpx.Response(200, json=turn_payload(state="refused"))
        ).submit_turn(
            device_id="d", session_id="s", turn_id="turn-1", audio=wav_bytes()
        )
        self.assertEqual(result.turn_id, "turn-1")
        self.assertEqual(result.state, "refused")
        self.assertEqual(result.language, "en")
        self.assertIsNone(result.case_id)
        self.assertTrue(result.has_slip)
        self.assertEqual(len(result.sources), 1)

    def test_unknown_extra_fields_do_not_break_the_client(self):
        payload = turn_payload(future_field="whatever")
        result = client_for(
            lambda request: httpx.Response(200, json=payload)
        ).submit_turn(device_id="d", session_id="s", turn_id="t", audio=wav_bytes())
        self.assertEqual(result.state, "answered")

    def test_missing_contract_field_is_an_invalid_response(self):
        payload = turn_payload()
        del payload["display_text"]
        with self.assertRaises(ApiError) as raised:
            client_for(
                lambda request: httpx.Response(200, json=payload)
            ).submit_turn(device_id="d", session_id="s", turn_id="t", audio=wav_bytes())
        self.assertEqual(raised.exception.code, "invalid_response")


class FailureTests(unittest.TestCase):
    """Transport and status failures become safe codes."""

    def test_timeouts_status_codes_and_transport_errors_map_to_codes(self):
        def slow(request):
            raise httpx.ReadTimeout("slow")

        def refused(request):
            raise httpx.ConnectError("refused")

        cases = (
            (slow, "timeout"),
            (refused, "unavailable"),
            (lambda request: httpx.Response(422), "rejected"),
            (lambda request: httpx.Response(503), "unavailable"),
            (lambda request: httpx.Response(200, content=b"not json"), "invalid_response"),
        )
        for handler, expected in cases:
            with self.subTest(code=expected):
                with self.assertRaises(ApiError) as raised:
                    client_for(handler).submit_turn(
                        device_id="d", session_id="s", turn_id="t", audio=wav_bytes()
                    )
                self.assertEqual(raised.exception.code, expected)

    def test_error_codes_stay_within_the_documented_set(self):
        self.assertEqual(ApiError("something odd").code, "unavailable")


class RouteTests(unittest.TestCase):
    """Only the three device-contract routes are ever requested."""

    def test_health_and_pending_use_their_documented_paths(self):
        seen = []

        def handler(request):
            seen.append(request.url.path)
            if request.url.path == HEALTH_PATH:
                return httpx.Response(200, json={"status": "ok", "stt_ready": True})
            return httpx.Response(200, json=[])

        client = client_for(handler)
        self.assertEqual(client.health()["status"], "ok")
        self.assertEqual(client.pending(), [])
        self.assertEqual(seen, [HEALTH_PATH, PENDING_PATH])

    def test_pending_is_empty_for_the_whole_mvp(self):
        client = client_for(lambda request: httpx.Response(200, json=[]))
        self.assertEqual(client.pending(), [])

    def test_a_path_outside_the_contract_is_rejected_before_any_request(self):
        def handler(request):
            raise AssertionError("no request should be sent")

        with self.assertRaises(ApiError) as raised:
            client_for(handler)._request("GET", "/v1/chat/completions", 1.0)
        self.assertEqual(raised.exception.code, "rejected")


class ReplyAudioTests(unittest.TestCase):
    """`reply_audio` is decoded exactly as the contract permits, or refused."""

    def test_null_audio_is_a_complete_turn_without_speech(self):
        self.assertIsNone(decode_reply_audio(None))

    def test_wav_data_url_decodes_to_the_original_bytes(self):
        audio = wav_bytes()
        self.assertEqual(decode_reply_audio(data_url(audio)), audio)

    def test_non_data_url_references_are_refused_rather_than_guessed(self):
        for value in (
            "https://example.gov.sg/reply.wav",
            "/var/lib/kaki/reply.wav",
            "data:audio/mpeg;base64," + b64encode(wav_bytes()).decode("ascii"),
            "data:audio/wav,not-base64-marked",
        ):
            with self.subTest(value=value[:32]), self.assertRaises(UnplayableAudio):
                decode_reply_audio(value)

    def test_malformed_payloads_are_refused(self):
        for value in (
            AUDIO_DATA_URL_PREFIX + "!!!not base64!!!",
            AUDIO_DATA_URL_PREFIX,
            AUDIO_DATA_URL_PREFIX + b64encode(b"RIFFnot-a-wav").decode("ascii"),
            AUDIO_DATA_URL_PREFIX + b64encode(wav_bytes(frames=0)).decode("ascii"),
        ):
            with self.subTest(value=value[:40]), self.assertRaises(UnplayableAudio):
                decode_reply_audio(value)


if __name__ == "__main__":
    unittest.main()
