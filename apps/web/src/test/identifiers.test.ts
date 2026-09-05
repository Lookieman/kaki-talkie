// v1.0 | 05-Sep-2026 | Verify native and fallback browser identifier generation.

import { describe, expect, it, vi } from "vitest";

import {
  createIdentifier,
  IdentifierCrypto,
} from "../simulator/identifiers";

describe("createIdentifier", () => {
  it("preserves the native randomUUID path when supported", () => {
    const randomUUID = vi.fn(() => "12345678-1234-4234-8234-123456789abc");
    const getRandomValues = vi.fn(() => {
      throw new Error("Fallback must not run when randomUUID is available.");
    });
    const cryptoApi: IdentifierCrypto = { randomUUID, getRandomValues };

    expect(createIdentifier("turn", cryptoApi)).toBe(
      "turn-12345678-1234-4234-8234-123456789abc",
    );
    expect(randomUUID).toHaveBeenCalledOnce();
    expect(getRandomValues).not.toHaveBeenCalled();
  });

  it("uses getRandomValues when randomUUID is unavailable", () => {
    const getRandomValues = vi.fn((bytes: Uint8Array) => {
      bytes.forEach((_, index) => {
        bytes[index] = index;
      });
      return bytes;
    });
    const cryptoApi: IdentifierCrypto = { getRandomValues };

    expect(createIdentifier("session", cryptoApi)).toBe(
      "session-00010203-0405-4607-8809-0a0b0c0d0e0f",
    );
    expect(getRandomValues).toHaveBeenCalledOnce();
  });
});
