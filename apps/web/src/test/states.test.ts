// v1.0 | 04-Sep-2026 | Verify the complete canned simulator state sequence.

import { describe, expect, it } from "vitest";

import { canTransition, DEVICE_STATES } from "../simulator/states";

describe("device states", () => {
  it("represents the five required states", () => {
    expect(DEVICE_STATES).toEqual(["idle", "listening", "thinking", "speaking", "printing"]);
  });

  it("allows one complete canned turn and return to idle", () => {
    const sequence = ["idle", "listening", "thinking", "speaking", "printing", "idle"] as const;
    for (let index = 0; index < sequence.length - 1; index += 1) {
      expect(canTransition(sequence[index], sequence[index + 1])).toBe(true);
    }
  });
});
