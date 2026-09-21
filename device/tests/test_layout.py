# v1.2 | 21-Sep-2026 | WP6.8: the released Auntie-register retry and failure copy.
# v1.1 | 20-Sep-2026 | WP6.4: retrying title and the connection-failure body.
# v1.0 | 16-Sep-2026 | WP6.1 display layout: states, wrapping, shrink, truncation, austerity.
"""Prove the kiosk display without a screen, fonts or pygame.

Layout is pure: it takes a text-measure function and returns positioned lines.
These tests inject a deterministic measure, so they hold on any machine and in
CI, and they cover the properties a reader a metre from a 1024x600 panel
depends on: text that fits, large sizes preferred, and nothing on screen that
design.md 9.2 forbids.
"""

import unittest

from kaki_device.display import layout  # WP6.4 copy constants
from kaki_device.display.layout import (
    BODY_SIZES,
    ELLIPSIS,
    MARGIN_X,
    MARGIN_Y,
    DisplayState,
    answer_frame,
    error_frame,
    idle_frame,
    recording_frame,
    thinking_frame,
    wrap,
)
from kaki_device.mock_io import fixed_measure

WIDTH, HEIGHT = 1024, 600
MEASURE = fixed_measure()


def line_height(size: int) -> int:
    """Mirror the layout's line height for assertions."""
    return int(size * 1.25)


class FrameTests(unittest.TestCase):
    """Every state renders, and carries its own state value."""

    def test_every_state_produces_a_non_empty_frame(self):
        frames = (
            idle_frame(WIDTH, HEIGHT, MEASURE),
            recording_frame(WIDTH, HEIGHT, MEASURE, 15),
            thinking_frame(WIDTH, HEIGHT, MEASURE),
            thinking_frame(WIDTH, HEIGHT, MEASURE, DisplayState.RETRYING),
            answer_frame(WIDTH, HEIGHT, MEASURE, "Open the SMS link from CDC."),
            error_frame(WIDTH, HEIGHT, MEASURE),
        )
        seen = set()
        for frame in frames:
            with self.subTest(state=frame.state):
                self.assertTrue(frame.lines)
                self.assertTrue(frame.text.strip())
                seen.add(frame.state)
        self.assertEqual(seen, set(DisplayState))

    def test_retrying_shows_its_own_title_and_stays_distinct(self):
        # WP6.4 added the frame; WP6.8 released the Auntie-register wording.
        thinking = thinking_frame(WIDTH, HEIGHT, MEASURE)
        retrying = thinking_frame(WIDTH, HEIGHT, MEASURE, DisplayState.RETRYING)
        self.assertIn(layout.RETRYING_TITLE, retrying.text)
        self.assertIn("Wait ah, checking again", retrying.text)
        self.assertIn(layout.THINKING_SUBTITLE, retrying.text)
        self.assertNotIn(layout.THINKING_TITLE, retrying.text)
        self.assertNotEqual(thinking.state, retrying.state)

    def test_the_connection_failure_body_replaces_the_generic_one(self):
        # WP6.4: shown once the same-turn_id retries are exhausted; the
        # wording is WP6.8's Auntie register (owner release, 21-Sep-2026).
        generic = error_frame(WIDTH, HEIGHT, MEASURE)
        connection = error_frame(WIDTH, HEIGHT, MEASURE, layout.CONNECTION_ERROR_BODY)
        self.assertIn(layout.ERROR_BODY, generic.text)
        self.assertIn("Don't worry. Press the button and we try again.", connection.text)
        self.assertNotIn(layout.ERROR_BODY, connection.text)
        self.assertEqual(connection.state, DisplayState.ERROR)

    def test_idle_and_recording_show_english_and_malay(self):
        idle = idle_frame(WIDTH, HEIGHT, MEASURE).text
        self.assertIn("Press the button", idle)
        self.assertIn("Tekan butang", idle)
        recording = recording_frame(WIDTH, HEIGHT, MEASURE, 12).text
        self.assertIn("Listening", recording)
        self.assertIn("12 s", recording)


class FittingTests(unittest.TestCase):
    """Answers fit the panel: wrap, then shrink, then truncate."""

    def test_short_answer_uses_the_largest_body_size(self):
        frame = answer_frame(WIDTH, HEIGHT, MEASURE, "Open the SMS link.")
        self.assertEqual(frame.lines[0].size, BODY_SIZES[0])
        self.assertFalse(frame.truncated)

    def test_wrapping_keeps_every_line_within_the_usable_width(self):
        text = ("Use your CDC vouchers at participating supermarkets and hawker "
                "stalls near your home before the expiry date.")
        frame = answer_frame(WIDTH, HEIGHT, MEASURE, text)
        for line in frame.lines:
            with self.subTest(line=line.text):
                self.assertLessEqual(MEASURE(line.text, line.size), WIDTH - 2 * MARGIN_X)

    def test_a_longer_answer_steps_the_size_down_before_truncating(self):
        text = " ".join(["Bring your identity card to the community centre."] * 8)
        frame = answer_frame(WIDTH, HEIGHT, MEASURE, text)
        self.assertLess(frame.lines[0].size, BODY_SIZES[0])
        self.assertFalse(frame.truncated)

    def test_an_overlong_answer_truncates_with_an_ellipsis_and_still_fits(self):
        text = " ".join(["Bring your identity card to the community centre."] * 40)
        frame = answer_frame(WIDTH, HEIGHT, MEASURE, text)
        self.assertTrue(frame.truncated)
        self.assertTrue(frame.text.rstrip().endswith(ELLIPSIS))
        self.assertLessEqual(
            len(frame.lines) * line_height(frame.lines[0].size), HEIGHT - 2 * MARGIN_Y
        )

    def test_no_frame_ever_overflows_the_panel(self):
        texts = ("", "Ya.", "Maaf, saya tidak ada maklumat rasmi tentang perkara itu.",
                 " ".join(["panjang"] * 200))
        for text in texts:
            frame = answer_frame(WIDTH, HEIGHT, MEASURE, text)
            with self.subTest(text=text[:24]):
                self.assertLessEqual(frame.lines[-1].y, HEIGHT)
                self.assertGreaterEqual(frame.lines[0].y, 0)

    def test_a_single_unbreakable_word_is_kept_whole(self):
        # Splitting a scheme name or a Malay word mid-word reads worse than one
        # long line the size step then handles.
        lines = wrap("Kementerian" * 12, BODY_SIZES[0], WIDTH - 2 * MARGIN_X, MEASURE)
        self.assertEqual(len(lines), 1)


class AusterityTests(unittest.TestCase):
    """design.md 9.2: the display carries the answer, not diagnostics."""

    def test_no_frame_shows_diagnostics_sources_or_controls(self):
        frames = (
            idle_frame(WIDTH, HEIGHT, MEASURE),
            recording_frame(WIDTH, HEIGHT, MEASURE, 5),
            thinking_frame(WIDTH, HEIGHT, MEASURE),
            answer_frame(WIDTH, HEIGHT, MEASURE, "Open the SMS link from CDC."),
            error_frame(WIDTH, HEIGHT, MEASURE),
        )
        forbidden = ("http", "Source:", "turn_id", "session", "dense", "intent",
                     "traceback", "error code", "127.0.0.1")
        for frame in frames:
            for token in forbidden:
                with self.subTest(state=frame.state, token=token):
                    self.assertNotIn(token.lower(), frame.text.lower())

    def test_the_error_frame_says_what_to_do_without_a_code(self):
        text = error_frame(WIDTH, HEIGHT, MEASURE).text
        self.assertIn("try again", text.lower())
        self.assertNotIn("timeout", text.lower())
        self.assertNotIn("unavailable", text.lower())


if __name__ == "__main__":
    unittest.main()
