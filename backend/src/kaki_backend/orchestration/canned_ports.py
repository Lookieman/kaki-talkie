# v1.1 | 05-Sep-2026 | Return packaged spoken fixtures without runtime synthesis.
# v1.0 | 04-Sep-2026 | Supply deterministic WP1 implementations of shared ports.

from base64 import b64encode  #v1.1
from functools import lru_cache  #v1.1
from importlib.resources import files  #v1.1

from kaki_backend.contracts.responses import SourceRecord


@lru_cache(maxsize=2)  #v1.1
def canned_audio(filename: str) -> str:  #v1.1
    if filename not in {"canned_reply.wav", "empty_audio.wav"}:  #v1.1
        raise ValueError("Unknown WP1 audio fixture")  #v1.1
    audio = files("kaki_backend").joinpath("fixtures").joinpath(filename).read_bytes()  #v1.1
    return "data:audio/wav;base64," + b64encode(audio).decode("ascii")  #v1.1


class CannedSttPort:
    def transcribe(self, audio: bytes) -> str:
        if not audio:
            raise ValueError("Canned STT requires non-empty audio")
        return "[canned audio; not interpreted]"


class CannedLlmPort:
    def generate(self, transcript: str) -> str:
        return "This is a KaKi-Talkie test reply. Your audio has not been interpreted."


class CannedTtsPort:
    def synthesize(self, reply_text: str) -> str | None:
        expected = CannedLlmPort().generate("[canned]")  #v1.1
        if reply_text != expected:  #v1.1
            raise ValueError("WP1 audio is available only for the canned reply")  #v1.1
        return canned_audio("canned_reply.wav")  #v1.1


class CannedRetrieverPort:
    def retrieve(
        self, original_query: str, normalized_query: str | None
    ) -> tuple[SourceRecord, ...]:
        return ()
