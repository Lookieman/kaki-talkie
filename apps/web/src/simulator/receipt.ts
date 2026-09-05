// v1.0 | 04-Sep-2026 | Format English slip text for a 32-character receipt.

export const RECEIPT_LINE_WIDTH = 32;

function wrapParagraph(paragraph: string, width: number): string[] {
  const words = paragraph.trim().split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let currentLine = "";

  for (const word of words) {
    if (word.length > width) {
      if (currentLine) {
        lines.push(currentLine);
        currentLine = "";
      }
      for (let offset = 0; offset < word.length; offset += width) {
        lines.push(word.slice(offset, offset + width));
      }
      continue;
    }
    const candidate = currentLine ? `${currentLine} ${word}` : word;
    if (candidate.length <= width) {
      currentLine = candidate;
    } else {
      lines.push(currentLine);
      currentLine = word;
    }
  }
  if (currentLine) {
    lines.push(currentLine);
  }
  return lines;
}

export function wrapReceipt(text: string, width = RECEIPT_LINE_WIDTH): string[] {
  if (!Number.isInteger(width) || width < 1) {
    throw new RangeError("Receipt width must be a positive integer.");
  }
  return text.split(/\r?\n/).flatMap((paragraph) => {
    const lines = wrapParagraph(paragraph, width);
    return lines.length > 0 ? lines : [""];
  });
}
