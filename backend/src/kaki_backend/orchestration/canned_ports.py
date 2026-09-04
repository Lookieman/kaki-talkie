# v1.0 | 04-Sep-2026 | Supply deterministic WP1 implementations of shared ports.

from kaki_backend.contracts.responses import SourceRecord


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
        return None


class CannedRetrieverPort:
    def retrieve(
        self, original_query: str, normalized_query: str | None
    ) -> tuple[SourceRecord, ...]:
        return ()
