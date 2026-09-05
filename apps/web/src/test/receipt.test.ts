// v1.0 | 04-Sep-2026 | Verify 40-word receipt wrapping without truncation.

import { describe, expect, it } from "vitest";

import { RECEIPT_LINE_WIDTH, wrapReceipt } from "../simulator/receipt";

describe("wrapReceipt", () => {
  it("fits a 40-word slip without truncating any word", () => {
    const words = Array.from({ length: 40 }, (_, index) => `step${index + 1}`);
    const lines = wrapReceipt(words.join(" "));

    expect(lines.every((line) => line.length <= RECEIPT_LINE_WIDTH)).toBe(true);
    expect(lines.join(" ").split(/\s+/)).toEqual(words);
  });

  it("preserves explicit line boundaries", () => {
    expect(wrapReceipt("KAKI-TALKIE TEST\nNo advice was generated.")).toEqual([
      "KAKI-TALKIE TEST",
      "No advice was generated.",
    ]);
  });
});
