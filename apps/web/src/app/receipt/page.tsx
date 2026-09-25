// v1.1 | 24-Sep-2026 | Show only a booking made after the page loaded; slip text wraps, never clips.
// v1.0 | 24-Sep-2026 | Pitch receipt page: the latest booking's slip, sized for a projector.

"use client";

/**
 * The standalone booking receipt for the projector.
 *
 * Polls `GET /api/admin/booking/latest` every 2 s and draws the newest
 * booking with the same slip component the simulator uses, whichever client
 * made the booking: the Pi or the simulator. The first poll records the
 * latest booking as a baseline, and the page shows "Waiting for booking..."
 * until a booking with a different case_id arrives (`BookingTrigger`), so an
 * old rehearsal booking never opens the pitch. A reload resets the baseline.
 * The page only reads; it never books, prints or changes state.
 *
 * Authentication follows the admin page: the application's admin bearer
 * token, asked for once and kept in this browser's localStorage under the
 * same key, so a browser that has opened /admin needs no second entry.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import type { BookingReceipt } from "../../simulator/bookingReceipt";
import { ReceiptProjector } from "../../simulator/ReceiptProjector";
import {
  BookingTrigger,
  parseLatestBooking,
  receiptForBooking,
} from "../../simulator/latestBooking";

const POLL_MS = 2000;
const TOKEN_KEY = "kaki-admin-token"; // shared with /admin
const LATEST_PATH = "/api/admin/booking/latest";

/** Read the stored token, or ask for it and store it (the admin page's pattern). */
function readToken(): string {
  const stored = readStored();
  if (stored) {
    return stored;
  }
  const entered = (window.prompt("Admin token (KAKI_ADMIN_TOKEN)") ?? "").trim();
  if (entered) {
    writeStored(entered);
  }
  return entered;
}

/** Return the stored token, or "" when storage is empty or unavailable. */
function readStored(): string {
  try {
    return window.localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

/** Store the token, ignoring a storage that refuses to keep it. */
function writeStored(value: string): void {
  try {
    window.localStorage.setItem(TOKEN_KEY, value);
  } catch {
    // Private window or blocked site data: the token lives for this page only.
  }
}

/** Forget a rejected token, so the next load asks for it again. */
function clearStored(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Nothing was stored, so nothing needs clearing.
  }
}

export default function ReceiptPage() {
  const [token, setToken] = useState("");
  const [receipt, setReceipt] = useState<BookingReceipt | null>(null);
  const [status, setStatus] = useState("Waiting for booking...");
  const trigger = useRef(new BookingTrigger());

  const refresh = useCallback(async () => {
    try {
      const response = await fetch(LATEST_PATH, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (response.status === 401 || response.status === 403) {
        clearStored();
        setStatus("Token rejected. Reload the page and enter it again.");
        return;
      }
      if (!response.ok) {
        return; // keep whatever is on screen; the next poll tries again
      }
      const shown = trigger.current.observe(parseLatestBooking(await response.json()));
      setReceipt(shown ? receiptForBooking(shown) : null);
      setStatus("Waiting for booking...");
    } catch {
      // Backend unreachable: keep the last slip on the projector and retry.
    }
  }, [token]);

  useEffect(() => {
    setToken(readToken());
  }, []);

  useEffect(() => {
    if (!token) {
      return;
    }
    void refresh();
    const interval = window.setInterval(() => void refresh(), POLL_MS);
    return () => window.clearInterval(interval);
  }, [refresh, token]);

  return (
    <ReceiptProjector
      receipt={receipt}
      message={token ? status : "No token entered. Reload the page to try again."}
    />
  );
}
