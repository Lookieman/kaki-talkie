# v1.1 | 10-Sep-2026 | Clean owner-curated markdown snapshots alongside HTML.
# v1.0 | 10-Sep-2026 | Convert snapshot HTML to clean heading-aware markdown blocks.
"""Turn snapshot content into clean, structured text for chunking.

Two cleaners share one block model: `clean_markdown` for the MVP's
owner-curated markdown snapshots (design.md 7.2 v1.2) and `clean_html` for
`capture: auto` HTML captures.

Retrieval must run over clean markdown/text, not raw markup or print-to-PDF
output (design.md 7.2). The extractor keeps headings and content blocks,
prefers the page's `main`/`article` region when one exists, and discards
navigation, scripts, styles, forms and other page furniture. It uses the
standard-library HTML parser so ingestion adds no third-party dependency.

Cleaning is deliberately conservative: pages whose content lives outside
ordinary content elements may clean poorly, and the owner inspects cleaned
output during validation (runbook 8.2 WP3.1 Test 1) rather than trusting it
blindly.
"""

import re
from dataclasses import dataclass
from html.parser import HTMLParser

SKIPPED_ELEMENTS = frozenset({
    "script", "style", "noscript", "template", "svg", "iframe", "canvas",
    "form", "button", "select", "nav", "header", "footer", "aside",
})
HEADING_ELEMENTS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
BLOCK_ELEMENTS = frozenset({
    "p", "li", "dt", "dd", "td", "th", "figcaption", "blockquote", "summary",
})
CONTENT_REGIONS = frozenset({"main", "article"})
VOID_ELEMENTS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "source", "track", "wbr",
})
MINIMUM_BLOCK_CHARACTERS = 3


@dataclass(frozen=True)
class CleanBlock:
    """One cleaned unit of page content: a heading (with level) or a text block."""

    kind: str
    text: str
    level: int = 0


class _ContentExtractor(HTMLParser):
    """Collect heading and content blocks, honouring skipped and content regions."""

    def __init__(self, *, restrict_to_content_region: bool) -> None:
        super().__init__(convert_charrefs=True)
        self._restrict = restrict_to_content_region
        self._skip_depth = 0
        self._region_depth = 0
        self._capture_element: str | None = None
        self._capture_depth = 0
        self._capture_parts: list[str] = []
        self.blocks: list[CleanBlock] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in VOID_ELEMENTS:
            if tag == "br" and self._capture_element is not None:
                self._capture_parts.append(" ")
            return
        if self._skip_depth > 0 or tag in SKIPPED_ELEMENTS:
            self._skip_depth += 1
            return
        if tag in CONTENT_REGIONS:
            self._region_depth += 1
            return
        if self._capture_element is not None:
            if tag == self._capture_element:
                self._capture_depth += 1
            return
        if self._restrict and self._region_depth == 0:
            return
        if tag in HEADING_ELEMENTS or tag in BLOCK_ELEMENTS:
            self._capture_element = tag
            self._capture_depth = 1
            self._capture_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_ELEMENTS:
            return
        if self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if tag in CONTENT_REGIONS and self._region_depth > 0:
            self._region_depth -= 1
            return
        if self._capture_element == tag:
            self._capture_depth -= 1
            if self._capture_depth == 0:
                self._emit(tag)

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and self._capture_element is not None:
            self._capture_parts.append(data)

    def _emit(self, tag: str) -> None:
        """Finish the open capture, keeping only meaningfully long text."""
        text = re.sub(r"\s+", " ", "".join(self._capture_parts)).strip()
        self._capture_element = None
        self._capture_parts = []
        if len(text) < MINIMUM_BLOCK_CHARACTERS:
            return
        if tag in HEADING_ELEMENTS:
            self.blocks.append(CleanBlock(kind="heading", text=text, level=int(tag[1])))
        else:
            self.blocks.append(CleanBlock(kind="paragraph", text=text))


def _extract(html: str, *, restrict_to_content_region: bool) -> list[CleanBlock]:
    """Run one extraction pass and drop consecutive duplicate blocks."""
    extractor = _ContentExtractor(restrict_to_content_region=restrict_to_content_region)
    extractor.feed(html)
    extractor.close()
    blocks: list[CleanBlock] = []
    for block in extractor.blocks:
        if blocks and blocks[-1] == block:
            continue
        blocks.append(block)
    return blocks


def clean_html(html: str) -> list[CleanBlock]:
    """Return the cleaned blocks of one page in document order.

    When the page declares a `main`/`article` region, only that region is
    used; otherwise the whole body contributes. Returns an empty list when
    the page yields no usable content, which callers must treat as a
    cleaning failure rather than storing an empty document.
    """
    restricted = _extract(html, restrict_to_content_region=True)
    if restricted:
        return restricted
    return _extract(html, restrict_to_content_region=False)


def blocks_to_markdown(blocks: list[CleanBlock]) -> str:
    """Render cleaned blocks as simple markdown for human inspection."""
    lines: list[str] = []
    for block in blocks:
        if block.kind == "heading":
            lines.append("#" * block.level + " " + block.text)
        else:
            lines.append(block.text)
    return "\n\n".join(lines) + "\n"


MAXIMUM_HEADING_LEVEL = 6  #v1.1


def clean_markdown(text: str) -> list[CleanBlock]:  #v1.1
    """Return the cleaned blocks of one owner-curated markdown snapshot.

    Lines starting with `#` become heading blocks whose level is the number
    of leading `#` characters, capped at six. Blank-line-separated runs of
    other lines become whitespace-normalised paragraph blocks. Headings and
    paragraphs below the minimum meaningful length are dropped, matching
    the HTML cleaner's guard.
    """  #v1.1
    blocks: list[CleanBlock] = []  #v1.1
    paragraph_lines: list[str] = []  #v1.1

    def flush_paragraph() -> None:  #v1.1
        joined = re.sub(r"\s+", " ", " ".join(paragraph_lines)).strip()  #v1.1
        paragraph_lines.clear()  #v1.1
        if len(joined) >= MINIMUM_BLOCK_CHARACTERS:  #v1.1
            blocks.append(CleanBlock(kind="paragraph", text=joined))  #v1.1

    for line in text.splitlines():  #v1.1
        stripped = line.strip()  #v1.1
        if not stripped:  #v1.1
            flush_paragraph()  #v1.1
            continue  #v1.1
        if stripped.startswith("#"):  #v1.1
            flush_paragraph()  #v1.1
            marker_length = len(stripped) - len(stripped.lstrip("#"))  #v1.1
            heading_text = stripped[marker_length:].strip()  #v1.1
            if len(heading_text) >= MINIMUM_BLOCK_CHARACTERS:  #v1.1
                blocks.append(CleanBlock(  #v1.1
                    kind="heading", text=heading_text,  #v1.1
                    level=min(marker_length, MAXIMUM_HEADING_LEVEL),  #v1.1
                ))  #v1.1
            continue  #v1.1
        paragraph_lines.append(stripped)  #v1.1
    flush_paragraph()  #v1.1
    return blocks  #v1.1
