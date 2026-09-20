# v1.1 | 20-Sep-2026 | WP6.4: retrying copy and the connection-failure body (placeholders).
# v1.0 | 16-Sep-2026 | WP6.1 display states and pure layout for the 1024x600 kiosk panel.
"""Turn device state into a frame of positioned text, with no drawing here.

Layout is pure so it can be proven on any machine: text measurement arrives as
an injected callable, and the result is a `Frame` of lines with sizes. The
pygame backend only blits what this produces. That split is what keeps the
display testable at Tier A with no screen, no fonts and no pygame.

design.md 9.2 keeps the display austere: `display_text` and nothing else. No
diagnostics, citations, menus or controls appear in any frame here.

Long answers are handled in one documented order: wrap at the current size,
and while the wrapped text is too tall, step the size down; below the smallest
size, keep the leading lines that fit and end with an ellipsis. The full
answer is always spoken, so truncation loses nothing the user cannot hear.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable

# Text metrics: (text, point size) -> pixel width. Injected so layout stays pure.
Measure = Callable[[str, int], int]

MARGIN_X = 64
MARGIN_Y = 48
LINE_SPACING = 1.25
ELLIPSIS = "..."

# Sizes are chosen for a reader standing about a metre from a 1024x600 panel;
# WP6.2 confirms them on the physical display and may retune these constants.
TITLE_SIZE = 56
BODY_SIZES = (52, 46, 40, 34)
CAPTION_SIZE = 32

COLOUR_BACKGROUND = (12, 18, 28)
COLOUR_PRIMARY = (245, 247, 250)
COLOUR_MUTED = (158, 170, 188)
COLOUR_ALERT = (255, 186, 120)

# TODO(ergonomics): placeholder EN/MS wording, for owner sign-off before the
# demo freeze. The Malay lines are plain-Latin and print-safe; the display
# never shows Hokkien or CJK (design.md 9.3 covers the printed slip).
IDLE_TITLE = "Press the button to talk"
IDLE_SUBTITLE = "Tekan butang untuk bercakap"
RECORDING_TITLE = "Listening..."
RECORDING_SUBTITLE = "Saya sedang mendengar"
THINKING_TITLE = "Thinking..."
THINKING_SUBTITLE = "Sila tunggu sebentar"
ERROR_TITLE = "Something went wrong"
ERROR_SUBTITLE = "Sila cuba lagi"
ERROR_BODY = "Please press the button and try again."
# TODO(WP6.8): placeholder WP6.4 copy, to be replaced during the ergonomics
# pass. RETRYING_TITLE shows while a timed-out turn is retried with the same
# turn_id; CONNECTION_ERROR_BODY shows once the retries are exhausted.
RETRYING_TITLE = "Checking again..."  #v1.1
CONNECTION_ERROR_BODY = "Cannot connect. Press the button to try again."  #v1.1


class DisplayState(str, Enum):
    """What the kiosk is doing, as far as the user can see.

    `RETRYING` is driven by the WP6.4 retry: a timed-out turn resubmitted
    with the same `turn_id` shows its own title so the user knows the kiosk
    is still working on the same question.
    """

    IDLE = "idle"
    RECORDING = "recording"
    THINKING = "thinking"
    RETRYING = "retrying"
    ANSWER = "answer"
    ERROR = "error"


@dataclass(frozen=True)
class TextLine:
    """One laid-out line: its text, point size, colour and baseline position."""

    text: str
    size: int
    colour: tuple[int, int, int]
    y: int


@dataclass(frozen=True)
class Frame:
    """A complete screen: a background colour and the lines to draw on it."""

    state: DisplayState
    background: tuple[int, int, int]
    lines: tuple[TextLine, ...]
    truncated: bool = False

    @property
    def text(self) -> str:
        """Return the frame's visible text, newline separated; used by tests."""
        return "\n".join(line.text for line in self.lines)


def wrap(text: str, size: int, width: int, measure: Measure) -> list[str]:
    """Break `text` into lines that fit `width` pixels at `size`.

    Splits on spaces. A single word wider than the line is kept whole rather
    than split mid-word, because a broken Malay or scheme name reads worse
    than one overhanging line the size step will fix.
    """
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if current and measure(candidate, size) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    return [line for line in lines if line] or [""]


def _line_height(size: int) -> int:
    return int(size * LINE_SPACING)


def _fit_body(
    text: str, width: int, height: int, measure: Measure,
) -> tuple[list[str], int, bool]:
    """Return body lines, the size they fit at, and whether text was dropped."""
    for size in BODY_SIZES:
        lines = wrap(text, size, width, measure)
        if len(lines) * _line_height(size) <= height:
            return lines, size, False
    size = BODY_SIZES[-1]
    lines = wrap(text, size, width, measure)
    room = max(1, height // _line_height(size))
    if len(lines) <= room:
        return lines, size, False
    kept = lines[:room]
    kept[-1] = kept[-1].rstrip() + ELLIPSIS
    return kept, size, True


def _stacked(
    entries: list[tuple[str, int, tuple[int, int, int]]], top: int,
) -> tuple[list[TextLine], int]:
    """Lay entries out top down, returning the lines and the next free y."""
    lines: list[TextLine] = []
    y = top
    for text, size, colour in entries:
        lines.append(TextLine(text=text, size=size, colour=colour, y=y))
        y += _line_height(size)
    return lines, y


def _simple_frame(
    state: DisplayState, title: str, subtitle: str, caption: str | None,
    height: int, colour: tuple[int, int, int] = COLOUR_PRIMARY,
) -> Frame:
    """Build a centred title/subtitle frame, with an optional caption line."""
    entries = [(title, TITLE_SIZE, colour), (subtitle, TITLE_SIZE, COLOUR_MUTED)]
    if caption:
        entries.append((caption, CAPTION_SIZE, COLOUR_MUTED))
    block = sum(_line_height(size) for _, size, _ in entries)
    lines, _ = _stacked(entries, max(MARGIN_Y, (height - block) // 2))
    return Frame(state=state, background=COLOUR_BACKGROUND, lines=tuple(lines))


def idle_frame(width: int, height: int, measure: Measure) -> Frame:
    """Show the resting prompt, in English and Malay."""
    return _simple_frame(DisplayState.IDLE, IDLE_TITLE, IDLE_SUBTITLE, None, height)


def recording_frame(
    width: int, height: int, measure: Measure, seconds_left: float,
) -> Frame:
    """Show that the kiosk is listening, with the remaining seconds."""
    caption = f"{max(0, int(seconds_left))} s"
    return _simple_frame(
        DisplayState.RECORDING, RECORDING_TITLE, RECORDING_SUBTITLE, caption, height,
    )


def thinking_frame(
    width: int, height: int, measure: Measure,
    state: DisplayState = DisplayState.THINKING,
) -> Frame:
    """Show that the backend is working.

    `RETRYING` carries its own (placeholder) title so the user sees the kiosk
    is checking again rather than stuck; the subtitle stays the same.
    """
    title = RETRYING_TITLE if state is DisplayState.RETRYING else THINKING_TITLE  #v1.1
    return _simple_frame(state, title, THINKING_SUBTITLE, None, height)


def answer_frame(width: int, height: int, measure: Measure, display_text: str) -> Frame:
    """Show `display_text` as large as it fits, wrapping and shrinking first."""
    usable_width = width - 2 * MARGIN_X
    usable_height = height - 2 * MARGIN_Y
    body, size, truncated = _fit_body(display_text, usable_width, usable_height, measure)
    block = len(body) * _line_height(size)
    lines, _ = _stacked(
        [(line, size, COLOUR_PRIMARY) for line in body],
        max(MARGIN_Y, (height - block) // 2),
    )
    return Frame(
        state=DisplayState.ANSWER, background=COLOUR_BACKGROUND,
        lines=tuple(lines), truncated=truncated,
    )


def error_frame(
    width: int, height: int, measure: Measure, body: str = ERROR_BODY,  #v1.1
) -> Frame:
    """Show a calm fixed message; stage error codes never reach the display.

    `body` lets the caller pick the connection-failure wording after the
    WP6.4 retries are exhausted; the default stays the generic message.
    """
    return _simple_frame(
        DisplayState.ERROR, ERROR_TITLE, ERROR_SUBTITLE, body, height,
        colour=COLOUR_ALERT,
    )
