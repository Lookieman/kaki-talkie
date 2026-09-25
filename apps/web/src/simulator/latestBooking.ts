// v1.1 | 24-Sep-2026 | Pitch receipt page: show only bookings made after the page loaded.
// v1.0 | 24-Sep-2026 | Pitch receipt page: parse the latest booking and build its slip.

import type { TurnResponse } from "../api-client/device";
import { buildBookingReceipt, type BookingReceipt } from "./bookingReceipt";

/**
 * The newest booking as `GET /api/admin/booking/latest` reports it.
 *
 * `completed_at` is the backend's UTC completion time. It becomes the slip's
 * "printed" line, so every screen shows the moment the booking happened
 * rather than the moment the page happened to poll.
 */
export interface LatestBooking {
  case_id: string;
  completed_at: string;
  slip_text: string;
  device_id: string;
}

/** Return the booking from an endpoint body, or null for "no booking yet" or a bad shape. */
export function parseLatestBooking(body: unknown): LatestBooking | null {
  if (typeof body !== "object" || body === null || !("booking" in body)) {
    return null;
  }
  const booking = (body as { booking: unknown }).booking;
  if (typeof booking !== "object" || booking === null) {
    return null;
  }
  const fields = booking as Record<string, unknown>;
  const names = ["case_id", "completed_at", "slip_text", "device_id"] as const;
  if (!names.every((name) => typeof fields[name] === "string" && fields[name] !== "")) {
    return null;
  }
  return {
    case_id: fields.case_id as string,
    completed_at: fields.completed_at as string,
    slip_text: fields.slip_text as string,
    device_id: fields.device_id as string,
  };
}

/**
 * Build the same receipt the simulator draws, from a stored booking.
 *
 * `buildBookingReceipt` reads only `case_id` and `slip_text` from a turn, so
 * the booking supplies those and the rest of the turn shape is filler.
 */
export function receiptForBooking(booking: LatestBooking): BookingReceipt | null {
  const turn: TurnResponse = {
    turn_id: booking.case_id,
    reply_audio: null,
    reply_text: "",
    display_text: "",
    slip_text: booking.slip_text,
    language: "en",
    state: "acted",
    case_id: booking.case_id,
    sources: [],
  };
  const printedAt = new Date(booking.completed_at);
  return buildBookingReceipt(turn, Number.isNaN(printedAt.getTime()) ? new Date() : printedAt);
}

/**
 * Decide which booking the projector shows: only one made after the page loaded.
 *
 * The first successful poll records the latest booking's `case_id` (or none)
 * as the baseline and shows nothing, so a rehearsal booking never opens the
 * pitch. Any later poll whose booking has a different `case_id` is shown.
 * A reload builds a new trigger, which resets the baseline.
 *
 * `case_id` has minute resolution (`EC-MMDD-HHMM`), so a new booking in the
 * same minute as the baseline booking shares its reference and stays hidden.
 */
export class BookingTrigger {
  private baselineRecorded = false;
  private baseline: string | null = null;

  /** Feed one successful poll; return the booking to show, or null to keep waiting. */
  observe(booking: LatestBooking | null): LatestBooking | null {
    if (!this.baselineRecorded) {
      this.baselineRecorded = true;
      this.baseline = booking?.case_id ?? null;
      return null;
    }
    if (booking === null || booking.case_id === this.baseline) {
      return null;
    }
    return booking;
  }
}
