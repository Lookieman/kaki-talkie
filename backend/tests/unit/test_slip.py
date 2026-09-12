# v1.1 | 12-Sep-2026 | Cover whole-step packing and the domain-only source line.
# v1.0 | 11-Sep-2026 | Verify the slip builder's word budget, provenance and structure.
"""Exercise the deterministic slip builder against the WP1 40-word contract."""

import unittest
from datetime import date, datetime, timezone

from kaki_backend.contracts.responses import SourceRecord
from kaki_backend.orchestration.slip import (
    ASK_AGAIN_LINE,
    MAX_SLIP_WORDS,
    SLIP_HEADING,
    build_slip,
    extract_steps,
)

SOURCE = SourceRecord(
    source_url="https://vouchers.cdc.gov.sg/residents/faq",
    page_title="CDC Vouchers: Frequently Asked Questions for Residents",
    captured_at=datetime(2026, 9, 10, 11, 6, 44, tzinfo=timezone.utc),
    source_updated_at=date(2026, 9, 1),
    content_hash="sha256:" + "0" * 64,
)

NUMBERED_REPLY = (
    "You can use your vouchers easily. 1. Open the SMS link on your phone. "
    "2. Choose the amount you want to spend at the stall. 3. Show the "
    "voucher code to the hawker before paying."
)


class ExtractStepsTests(unittest.TestCase):
    """Steps are whole sentences; nothing is cut mid-phrase."""

    def test_numbered_reply_yields_whole_untruncated_steps(self):
        steps = extract_steps(NUMBERED_REPLY)
        self.assertEqual(steps[0], "Open the SMS link on your phone.")
        self.assertEqual(steps[1], "Choose the amount you want to spend at the stall.")
        for step in steps:
            self.assertTrue(step.endswith("."))

    def test_prose_reply_falls_back_to_sentences(self):
        steps = extract_steps("Visit the portal today. Bring your card. Ask for help.")
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[1], "Bring your card.")

    def test_long_step_is_never_clipped_into_a_fragment(self):
        # The owner-reported "contact the." defect: a step longer than the old
        # seven-word cap must come back whole, not clipped and re-punctuated.
        reply = "1. If you need further help, contact the Singpass Helpdesk at 6335 3533."
        self.assertEqual(
            extract_steps(reply),
            ["If you need further help, contact the Singpass Helpdesk at 6335 3533."],
        )

    def test_up_to_four_steps_are_returned(self):
        reply = "1. One thing. 2. Two thing. 3. Three thing. 4. Four thing. 5. Five thing."
        self.assertEqual(len(extract_steps(reply)), 4)

    def test_existing_punctuation_is_not_doubled(self):
        self.assertEqual(extract_steps("1. Is this right? 2. Yes!"), ["Is this right?", "Yes!"])


class BuildSlipTests(unittest.TestCase):
    """The whole slip fits the contract and carries application provenance."""

    def test_slip_structure_and_word_budget(self):
        slip = build_slip(extract_steps(NUMBERED_REPLY), SOURCE)
        lines = slip.splitlines()
        self.assertEqual(lines[0], SLIP_HEADING)
        self.assertEqual(lines[-1], ASK_AGAIN_LINE)
        self.assertLessEqual(len(slip.split()), MAX_SLIP_WORDS)

    def test_source_line_is_the_domain_alone_never_the_url(self):
        slip = build_slip(["Open the SMS link."], SOURCE)
        self.assertIn("Source: vouchers.cdc.gov.sg", slip)
        self.assertNotIn("http", slip)
        self.assertNotIn("/residents/faq", slip)

    def test_page_title_never_reaches_the_slip(self):
        for title in ("CDC Vouchers for residents",
                      "I forgot my Singpass password. How do I reset it?",
                      "CDC Vouchers: Frequently Asked Questions for Residents"):
            slip = build_slip([], SOURCE.model_copy(update={"page_title": title}))
            self.assertIn("Source: vouchers.cdc.gov.sg", slip)
            for word in title.replace(":", " ").split():
                self.assertNotIn(word, slip.splitlines()[1], msg=title)

    def test_source_checked_date_derives_from_captured_at(self):
        slip = build_slip(["Open the SMS link."], SOURCE)
        self.assertIn("Source checked: 10-Sep-2026", slip)

    def test_steps_that_do_not_fit_are_omitted_whole(self):
        steps = ["Short first step.", " ".join(f"word{i}" for i in range(30)) + "."]
        slip = build_slip(steps, SOURCE)
        self.assertLessEqual(len(slip.split()), MAX_SLIP_WORDS)
        self.assertIn("Short first step.", slip)
        self.assertNotIn("word0", slip)

    def test_no_printed_step_is_ever_a_fragment_of_its_input(self):
        for steps in ([" ".join(f"word{i}" for i in range(30)) + "."] * 4,
                      extract_steps(NUMBERED_REPLY), ["A.", "B.", "C.", "D."]):
            slip = build_slip(steps, SOURCE)
            self.assertLessEqual(len(slip.split()), MAX_SLIP_WORDS)
            printed = slip.splitlines()[1:-3]
            for line in printed:
                self.assertIn(line, steps)

    def test_empty_steps_still_produce_a_valid_provenanced_slip(self):
        slip = build_slip([], SOURCE)
        self.assertLessEqual(len(slip.split()), MAX_SLIP_WORDS)
        self.assertIn("Source checked:", slip)
        self.assertIn(ASK_AGAIN_LINE, slip)

    def test_four_steps_are_packed_when_they_fit(self):
        slip = build_slip(["One two.", "Three four.", "Five six.", "Seven eight."], SOURCE)
        self.assertEqual(len(slip.splitlines()), 8)
        self.assertLessEqual(len(slip.split()), MAX_SLIP_WORDS)


if __name__ == "__main__":
    unittest.main()
