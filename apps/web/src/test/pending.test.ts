// v1.0 | 18-Sep-2026 | WP6.6: nudge parsing and once-only surfacing (WP6-AT-16 client half).
import { describe, expect, it } from "vitest";

import { NudgeTracker, parsePendingItems, PENDING_POLL_SECONDS } from "../simulator/pending";

const NUDGE = {
  id: "cdc-vouchers-available",
  kind: "nudge",
  text: "Good news: new CDC vouchers are available.",
  language: "en",
  audio: null,
  pushed_at: "2026-09-18T09:00:00.000+00:00",
};

describe("parsePendingItems", () => {
  it("keeps well-formed items and defaults optional fields", () => {
    const items = parsePendingItems([NUDGE, { id: "x", text: "y" }]);
    expect(items).toHaveLength(2);
    expect(items[1]).toEqual({
      id: "x", kind: "nudge", text: "y", language: "en", audio: null, pushed_at: null,
    });
  });

  it("returns nothing for the empty list, junk shapes and non-arrays", () => {
    expect(parsePendingItems([])).toEqual([]);
    expect(parsePendingItems([{ text: 42 }, null, "nudge"])).toEqual([]);
    expect(parsePendingItems({ id: "x" })).toEqual([]);
    expect(parsePendingItems(undefined)).toEqual([]);
  });
});

describe("NudgeTracker", () => {
  it("surfaces one delivery exactly once across repeated polls", () => {
    const tracker = new NudgeTracker();
    expect(tracker.takeNew([NUDGE])).toHaveLength(1);
    for (let poll = 0; poll < 20; poll += 1) {
      expect(tracker.takeNew([NUDGE])).toEqual([]);
    }
  });

  it("surfaces a re-pushed rehearsal, which carries a new pushed_at", () => {
    const tracker = new NudgeTracker();
    tracker.takeNew([NUDGE]);
    const rehearsed = { ...NUDGE, pushed_at: "2026-09-18T10:30:00.000+00:00" };
    expect(tracker.takeNew([rehearsed])).toHaveLength(1);
    expect(tracker.takeNew([rehearsed])).toEqual([]);
  });

  it("reset clears the memory for a fresh demo run", () => {
    const tracker = new NudgeTracker();
    tracker.takeNew([NUDGE]);
    tracker.reset();
    expect(tracker.takeNew([NUDGE])).toHaveLength(1);
  });
});

describe("PENDING_POLL_SECONDS", () => {
  it("is the documented 3-second constant", () => {
    expect(PENDING_POLL_SECONDS).toBe(3);
  });
});
