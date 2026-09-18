# v1.0 | 16-Sep-2026 | WP6.1 fullscreen pygame renderer; blits frames from layout.py.
"""Draw layout frames full screen, and nothing more.

This module is the only place pygame is imported, and it holds no layout
decisions: `layout.py` decides what the screen says and where, this blits it.
That is why Tier A can prove the display without a screen, fonts or pygame.

pygame is an optional extra (`device[display]`, or `python3-pygame` on the
Pi), so importing this module without it raises a clear error instead of an
opaque ImportError deep in a turn.

SDL picks its driver at runtime: under the Pi's desktop session it uses X11,
and with the desktop disabled it renders straight to KMS/DRM. No code changes
either way, which is what keeps the WP6.4 boot-time decision open.
"""

from typing import Any

from kaki_device.display.layout import COLOUR_BACKGROUND, Frame, Measure


class DisplayUnavailable(RuntimeError):
    """Signal that no display backend could be opened."""


def _import_pygame() -> Any:
    """Import pygame or explain how to install it for this machine."""
    try:
        import pygame
    except ImportError:
        raise DisplayUnavailable(
            "pygame is not installed: pip install -e 'device[display]' on the Mac, "
            "or sudo apt install python3-pygame on the Pi (setup.md 30.5)."
        ) from None
    return pygame


class PygameDisplay:
    """Own one fullscreen window and blit frames onto it."""

    def __init__(self, width: int, height: int, *, fullscreen: bool = True,
                 font_name: str | None = None) -> None:
        """Open the display and load the fonts the layout sizes need.

        Side effects: initialises pygame's display and font modules, hides the
        cursor and creates a window. Raises DisplayUnavailable when SDL cannot
        open a display, so a headless run fails loudly at startup.
        """
        self._pygame = _import_pygame()
        self._fonts: dict[int, Any] = {}
        self._font_name = font_name
        try:
            self._pygame.display.init()
            self._pygame.font.init()
            flags = self._pygame.FULLSCREEN if fullscreen else 0
            self._surface = self._pygame.display.set_mode((width, height), flags)
            self._pygame.mouse.set_visible(False)
        except Exception as error:  # pygame raises its own error types
            raise DisplayUnavailable(f"cannot open a display: {error}") from None

    def _font(self, size: int) -> Any:
        """Return a cached font at `size`; fonts are expensive to build per frame."""
        if size not in self._fonts:
            self._fonts[size] = self._pygame.font.SysFont(self._font_name, size)
        return self._fonts[size]

    def measure(self) -> Measure:
        """Return the text-measure callable `layout` needs for this screen's fonts."""
        def measure_text(text: str, size: int) -> int:
            return self._font(size).size(text)[0]

        return measure_text

    def show(self, frame: Frame) -> None:
        """Draw one frame, replacing the previous screen contents."""
        self._surface.fill(frame.background or COLOUR_BACKGROUND)
        width = self._surface.get_width()
        for line in frame.lines:
            if not line.text:
                continue
            rendered = self._font(line.size).render(line.text, True, line.colour)
            self._surface.blit(rendered, rendered.get_rect(center=(width // 2, line.y)))
        self._pygame.display.flip()

    def close(self) -> None:
        """Release the display; safe to call more than once."""
        try:
            self._pygame.display.quit()
        except Exception:  # a second close, or an already-dead display
            pass
