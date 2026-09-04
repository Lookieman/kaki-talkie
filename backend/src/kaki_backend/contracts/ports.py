# v1.0 | 04-Sep-2026 | Define replaceable WP1 inference and retrieval ports.

from typing import Protocol

from kaki_backend.contracts.responses import SourceRecord


class SttPort(Protocol):
    def transcribe(self, audio: bytes) -> str:
        """Return a transcript for normalised or client-supplied audio."""


class LlmPort(Protocol):
    def generate(self, transcript: str) -> str:
        """Return conversational response text for the current turn."""


class TtsPort(Protocol):
    def synthesize(self, reply_text: str) -> str | None:
        """Return an audio reference when speech output is available."""


class RetrieverPort(Protocol):
    def retrieve(
        self, original_query: str, normalized_query: str | None
    ) -> tuple[SourceRecord, ...]:
        """Return application-owned evidence provenance for a bounded query."""
