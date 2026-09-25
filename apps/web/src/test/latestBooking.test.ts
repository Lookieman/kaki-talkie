// v1.1 | 24-Sep-2026 | Receipt page: baseline trigger and fit-to-viewport zoom.
// v1.0 | 24-Sep-2026 | Pitch receipt page: parse the latest booking and build its slip.

import { afterEach, describe, expect, it, vi } from "vitest";

import { RECEIPT_SUBTITLE, RECEIPT_TITLE } from "../simulator/bookingReceipt";
import {
  BookingTrigger,
  parseLatestBooking,
  receiptForBooking,
} from "../simulator/latestBooking";
import { fitToViewport } from "../simulator/ReceiptProjector";

const BOOKING = {
  case_id: "EC-0924-1424",
  completed_at: "2026-09-24T14:24:31.274+00:00",
  slip_text: "KAKI-TALKIE BOOKING\nGo to the main office, level 1.",
  device_id: "kaki-pi-01",
};

describe("parseLatestBooking", () => {
  it("returns null before any booking", () => {
    expect(parseLatestBooking({ booking: null })).toBeNull();
  });

  it("returns the booking fields", () => {
    expect(parseLatestBooking({ booking: BOOKING })).toEqual(BOOKING);
  });

  it("rejects a malformed body rather than drawing half a slip", () => {
    expect(parseLatestBooking(null)).toBeNull();
    expect(parseLatestBooking({ booking: { ...BOOKING, case_id: 7 } })).toBeNull();
  });
});

describe("receiptForBooking", () => {
  it("draws the simulator's receipt from the stored booking", () => {
    const receipt = receiptForBooking(BOOKING);
    expect(receipt!.title).toBe(RECEIPT_TITLE);
    expect(receipt!.subtitle).toBe("your booking slip");
    expect(RECEIPT_SUBTITLE).toBe("your booking slip");
    expect(receipt!.caseId).toBe("EC-0924-1424");
    expect(receipt!.bodyLines).toContain("KAKI-TALKIE BOOKING");
    expect(receipt!.printedAt).toContain("2026");
  });
});

describe("BookingTrigger", () => {
  const later = { ...BOOKING, case_id: "EC-0924-2215" };

  it("waits on load even when an older booking exists", () => {
    const trigger = new BookingTrigger();
    expect(trigger.observe(BOOKING)).toBeNull();
    expect(trigger.observe(BOOKING)).toBeNull();
  });

  it("shows a booking whose case_id differs from the baseline", () => {
    const trigger = new BookingTrigger();
    trigger.observe(BOOKING);
    expect(trigger.observe(later)).toEqual(later);
    expect(trigger.observe(later)).toEqual(later); // stays on screen
  });

  it("shows the first booking when there was none at load", () => {
    const trigger = new BookingTrigger();
    expect(trigger.observe(null)).toBeNull();
    expect(trigger.observe(null)).toBeNull();
    expect(trigger.observe(BOOKING)).toEqual(BOOKING);
  });

  it("a reload (new trigger) takes the shown booking as its new baseline", () => {
    const first = new BookingTrigger();
    first.observe(BOOKING);
    first.observe(later);
    const reloaded = new BookingTrigger();
    expect(reloaded.observe(later)).toBeNull();
  });
});

describe("fitToViewport", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function paper(width: number, height: number) {
    return {
      style: { zoom: "" },
      getBoundingClientRect: () => ({ width, height }),
    } as unknown as HTMLElement;
  }

  it("is limited by height at 1280x720 so the whole slip is visible", () => {
    vi.stubGlobal("window", { innerWidth: 1280, innerHeight: 720 });
    const element = paper(288, 610);
    fitToViewport(element);
    const zoom = Number(element.style.zoom);
    expect(610 * zoom).toBeLessThanOrEqual(720);
    expect(288 * zoom).toBeLessThanOrEqual(1280);
    expect(zoom).toBeCloseTo((720 * 0.94) / 610, 5);
  });

  it("scales up at 1920x1080 and never past the cap", () => {
    vi.stubGlobal("window", { innerWidth: 1920, innerHeight: 1080 });
    const element = paper(288, 610);
    fitToViewport(element);
    expect(610 * Number(element.style.zoom)).toBeLessThanOrEqual(1080);
    const small = paper(100, 100);
    fitToViewport(small);
    expect(small.style.zoom).toBe("2.2");
  });
});
