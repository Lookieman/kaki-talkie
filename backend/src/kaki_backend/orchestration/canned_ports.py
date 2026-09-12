# v1.6 | 12-Sep-2026 | Return a typed grounded reply for the shared port protocol.
# v1.5 | 11-Sep-2026 | Match the WP3.3 port shapes: rewrite, evidence and readiness.
# v1.4 | 09-Sep-2026 | Report canned TTS readiness for the shared port protocol.
# v1.3 | 09-Sep-2026 | Report canned LLM readiness for the shared port protocol.
# v1.2 | 07-Sep-2026 | Return typed canned STT results without invented language evidence.
# v1.1 | 05-Sep-2026 | Return packaged spoken fixtures without runtime synthesis.
# v1.0 | 04-Sep-2026 | Supply deterministic WP1 implementations of shared ports.

"""Keep deterministic demo ports and prerecorded speech independent of model services."""

from base64 import b64encode  #v1.1
from functools import lru_cache  #v1.1
from importlib.resources import files  #v1.1

from kaki_backend.contracts.ports import EvidenceChunk, GroundedReply, Transcription  #v1.6


@lru_cache(maxsize=2)  #v1.1
def canned_audio(filename: str) -> str:  #v1.1
    """Encode one allowlisted packaged recording; reject arbitrary file paths."""
    if filename not in {"canned_reply.wav", "empty_audio.wav"}:  #v1.1
        raise ValueError("Unknown WP1 audio fixture")  #v1.1
    audio = files("kaki_backend").joinpath("fixtures").joinpath(filename).read_bytes()  #v1.1
    return "data:audio/wav;base64," + b64encode(audio).decode("ascii")  #v1.1


class CannedSttPort:
    """Supply an explicit canned transcript without pretending to recognise speech."""

    def ready(self) -> bool:
        """Report that canned STT needs no external runtime."""
        return True

    def transcribe(self, audio: bytes) -> Transcription:
        """Return the canned result for non-empty input; invent no detection evidence."""
        if not audio:
            raise ValueError("Canned STT requires non-empty audio")
        return Transcription(text="[canned audio; not interpreted]")


class CannedLlmPort:
    """Supply the fixed WP1 reply while real generation remains deferred."""

    def ready(self) -> bool:
        """Report that canned generation needs no external runtime."""
        return True

    def generate(self, transcript: str) -> str:  #v1.6
        """Ignore recognised text and keep the prerecorded reply contract."""
        return "This is a KaKi-Talkie test reply. Your audio has not been interpreted."

    def generate_grounded(self, transcript: str, *, evidence: str) -> GroundedReply:  #v1.6
        """Return the canned reply with no citation; canned mode cites nothing."""
        return GroundedReply(text=self.generate(transcript), cited_index=None)

    def rewrite_query(self, transcript: str) -> str:  #v1.5
        """Return the transcript unchanged; canned mode never rewrites queries."""
        return transcript


class CannedTtsPort:
    """Return only the recording matching the exact canned reply."""

    def ready(self) -> bool:
        """Report that canned speech needs no external engine."""
        return True

    def synthesize(self, reply_text: str) -> str | None:
        """Return canned speech or reject text for which no recording exists."""
        expected = CannedLlmPort().generate("[canned]")  #v1.1
        if reply_text != expected:  #v1.1
            raise ValueError("WP1 audio is available only for the canned reply")  #v1.1
        return canned_audio("canned_reply.wav")  #v1.1


class CannedRetrieverPort:
    """Keep retrieval inert when the grounded configuration is not selected."""
    def ready(self) -> bool:  #v1.5
        """Report readiness; the inert retriever has nothing that can fail."""
        return True

    def retrieve(
        self, original_query: str, normalized_query: str | None
    ) -> tuple[EvidenceChunk, ...]:  #v1.5
        """Return no evidence and make no external requests."""
        return ()
