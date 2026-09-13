// v1.0 | 13-Sep-2026 | Apply the client print policy to a turn response (WP4.2).

import type { TurnResponse } from "../api-client/device";

// design.md 9.3: the backend always produces slip_text and the device applies
// its configured print policy. The Pi applies the same rule at WP6.3.
export const PRINT_POLICIES = ["auto", "on_request"] as const;

export type PrintPolicy = (typeof PRINT_POLICIES)[number];

export const DEFAULT_PRINT_POLICY: PrintPolicy = "auto";

// `auto` prints any non-empty slip. `on_request` prints only a print request:
// an `acted` turn with a non-empty slip, which only print_previous returns.
// A repeat carries an empty slip, so it never reprints under either policy.
export function shouldPrint(
  policy: PrintPolicy,
  response: Pick<TurnResponse, "state" | "slip_text">,
): boolean {
  if (!response.slip_text) {
    return false;
  }
  return policy === "auto" || response.state === "acted";
}
