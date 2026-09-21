// v1.0 | 21-Sep-2026 | WP6.7 booking receipt composition from turn fields.

import { describe, expect, it } from "vitest";

import { TurnResponse } from "../api-client/device";
import {
  FOLLOW_UP_LINE,
  QR_CAPTION,
  RECEIPT_TITLE,
  buildBookingReceipt,
  formatPrintedAt,
} from "../simulator/bookingReceipt";

function turn(overrides: Partial<TurnResponse> = {}): TurnResponse {
  return {
    turn_id: "turn-1",
    reply_audio: null,
    reply_text: "Okay, don't worry. Go to the main office on level 1.",
    display_text: "Okay, don't worry. Go to the main office on level 1.",
    slip_text:
      "KAKI-TALKIE BOOKING\nGo to the main office, level 1.\nBring your NRIC.",
    language: "en",
    state: "acted",
    case_id: "EC-0920-1356",
    sources: [],
    ...overrides,
  };
}

describe("buildBookingReceipt", () => {
  it("renders the case reference and slip body from the turn", () => {
    const receipt = buildBookingReceipt(turn());
    expect(receipt).not.toBeNull();
    expect(receipt!.caseId).toBe("EC-0920-1356");
    expect(receipt!.bodyLines).toContain("KAKI-TALKIE BOOKING");
    expect(receipt!.bodyLines.join(" ")).toContain("main office");
    expect(receipt!.title).toBe(RECEIPT_TITLE);
  });

  it("wraps the body to the 58 mm column width", () => {
    const long = "A booking line that is definitely longer than thirty-two characters.";
    const receipt = buildBookingReceipt(turn({ slip_text: long }));
    for (const line of receipt!.bodyLines) {
      expect(line.length).toBeLessThanOrEqual(32);
    }
  });

  // execution-plan.md 7: the QR block and the follow-up line are printed
  // illustration. They must be constants, never read from the turn.
  it("carries the illustration blocks as fixed text", () => {
    const receipt = buildBookingReceipt(turn());
    expect(receipt!.qrCaption).toBe(QR_CAPTION);
    expect(receipt!.followUp).toBe(FOLLOW_UP_LINE);
    expect(receipt!.qrLines.length).toBeGreaterThan(0);
  });

  it("returns null for a turn that booked nothing", () => {
    expect(buildBookingReceipt(turn({ case_id: null }))).toBeNull();
    expect(buildBookingReceipt(turn({ case_id: null, state: "answered" }))).toBeNull();
  });
});

describe("formatPrintedAt", () => {
  it("reads as a date and a twelve-hour time", () => {
    const formatted = formatPrintedAt(new Date(2026, 8, 20, 13, 56));
    expect(formatted).toContain("2026");
    expect(formatted).toMatch(/\b(am|pm)\b/);
  });
});
