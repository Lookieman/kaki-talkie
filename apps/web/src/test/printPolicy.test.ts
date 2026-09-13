// v1.0 | 13-Sep-2026 | Verify the WP4-AT-06 client print policy rule.

import { describe, expect, it } from "vitest";

import { DEFAULT_PRINT_POLICY, PRINT_POLICIES, shouldPrint } from "../simulator/printPolicy";

const answered = { state: "answered", slip_text: "KAKI-TALKIE HELP\nSource: vouchers.cdc.gov.sg" } as const;
const refused = { state: "refused", slip_text: "KAKI-TALKIE REFERRAL" } as const;
const repeated = { state: "acted", slip_text: "" } as const;
const printRequest = { state: "acted", slip_text: answered.slip_text } as const;
const failed = { state: "failed", slip_text: "" } as const;

describe("print policy", () => {
  it("offers auto and on_request, defaulting to auto", () => {
    expect(PRINT_POLICIES).toEqual(["auto", "on_request"]);
    expect(DEFAULT_PRINT_POLICY).toBe("auto");
  });

  it("on_request prints nothing until a print is requested (WP4-AT-06)", () => {
    expect(shouldPrint("on_request", answered)).toBe(false);
    expect(shouldPrint("on_request", refused)).toBe(false);
    expect(shouldPrint("on_request", repeated)).toBe(false);
    expect(shouldPrint("on_request", printRequest)).toBe(true);
  });

  it("auto prints every slip but never reprints on a repeat", () => {
    expect(shouldPrint("auto", answered)).toBe(true);
    expect(shouldPrint("auto", refused)).toBe(true);
    expect(shouldPrint("auto", printRequest)).toBe(true);
    expect(shouldPrint("auto", repeated)).toBe(false);
  });

  it("never prints an empty slip", () => {
    expect(shouldPrint("auto", failed)).toBe(false);
    expect(shouldPrint("on_request", failed)).toBe(false);
  });
});
