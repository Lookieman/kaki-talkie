# v1.0 | 12-Sep-2026 | Verify cited-evidence selection and its deterministic fallback.
"""Exercise attribution selection: model citation first, overlap as the fallback."""

import unittest
from datetime import datetime, timezone

from kaki_backend.contracts.ports import EvidenceChunk
from kaki_backend.contracts.responses import SourceRecord
from kaki_backend.orchestration.citation import select_cited_evidence


def chunk(chunk_id: str, source_id: str, text: str, heading: str = "") -> EvidenceChunk:
    """Return one evidence chunk with throwaway provenance."""
    return EvidenceChunk(
        chunk_id=chunk_id, source_id=source_id,
        heading_path=(heading,) if heading else (), text=text,
        source=SourceRecord(
            source_url=f"https://www.example.gov.sg/{source_id}",
            page_title=f"About {source_id}",
            captured_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
        ),
        fused_score=0.03,
    )


CDC = chunk("c1", "cdc-vouchers-residents",
            "If you have problems with Singpass, visit the Singpass website for help.",
            "I have problems with my Singpass account")
SINGPASS = chunk("c2", "singpass-support",
                 "Visit the Singpass Portal. Select 'Services' on the top scroll bar. "
                 "Select 'Reset password'. Enter your NRIC or FIN details.",
                 "I have forgotten my Singpass password")
CHAS = chunk("c3", "chas-about", "CHAS subsidises visits to participating clinics.")
EVIDENCE = (CDC, SINGPASS, CHAS)

SINGPASS_ANSWER = ("Visit the Singpass Portal. Select 'Services' on the top scroll bar. "
                   "Select 'Reset password'.")


class SelectCitedEvidenceTests(unittest.TestCase):
    """A valid model citation wins; otherwise overlap decides, then rank one."""

    def test_valid_citation_is_honoured(self):
        self.assertIs(select_cited_evidence(EVIDENCE, SINGPASS_ANSWER, 2), SINGPASS)
        self.assertIs(select_cited_evidence(EVIDENCE, SINGPASS_ANSWER, 3), CHAS)

    def test_overlap_beats_rank_one_when_no_citation_is_given(self):
        self.assertIs(select_cited_evidence(EVIDENCE, SINGPASS_ANSWER, None), SINGPASS)

    def test_out_of_range_or_zero_citation_falls_back_to_overlap(self):
        for index in (0, 4, 99, -1):
            self.assertIs(
                select_cited_evidence(EVIDENCE, SINGPASS_ANSWER, index), SINGPASS,
                msg=index,
            )

    def test_unrelated_reply_falls_back_to_rank_one(self):
        self.assertIs(select_cited_evidence(EVIDENCE, "Zzz qqq xyzzy.", None), CDC)

    def test_common_words_alone_do_not_decide_attribution(self):
        # A reply of nothing but stop words shares no content words, so the
        # fallback must not pretend it matched a chunk.
        self.assertIs(select_cited_evidence(EVIDENCE, "You can do this with the.", None), CDC)

    def test_no_evidence_returns_none(self):
        self.assertIsNone(select_cited_evidence((), SINGPASS_ANSWER, 1))

    def test_selection_is_deterministic(self):
        first = select_cited_evidence(EVIDENCE, SINGPASS_ANSWER, None)
        for _ in range(5):
            self.assertIs(select_cited_evidence(EVIDENCE, SINGPASS_ANSWER, None), first)


if __name__ == "__main__":
    unittest.main()
