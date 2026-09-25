// v1.2 | 25-Sep-2026 | QR image replaces the placeholder; follow-up asks about the voucher.
// v1.1 | 24-Sep-2026 | Pitch receipt: subtitle reads "your booking slip".
// v1.0 | 21-Sep-2026 | WP6.7 booking receipt: turn fields plus printed illustration.

import { TurnResponse } from "../api-client/device";
import { wrapReceipt } from "./receipt";

/**
 * Compose the 58 mm booking receipt (WP6-AT-20).
 *
 * Everything factual comes from the turn: `slip_text` is the body and
 * `case_id` the reference. Nothing here invents content, and no new response
 * field was added — the receipt renders from the WP1 contract as it stands
 * (owner decision, 21-Sep-2026).
 *
 * The header, the QR block and the follow-up line are **printed
 * illustration** (execution-plan.md 7): they show what the printed artefact
 * would look like, and they create no case, no stored follow-up state and no
 * live-pipeline branch. They are constants here precisely so that no reader
 * mistakes them for something the backend promised.
 *
 * `printedAt` defaults to the moment the slip is drawn, taken from the
 * browser clock, because the turn carries no timestamp. The /receipt page
 * passes the booking's completion time instead.
 */

export const RECEIPT_TITLE = "Your KaKi Talkie";
export const RECEIPT_SUBTITLE = "your booking slip";
export const RECEIPT_KAKI_LABEL = "Your kaki";
export const RECEIPT_KAKI_VALUE = "Community centre staff";
export const RECEIPT_CASE_LABEL = "Case ID";
export const QR_PLACEHOLDER_LINES = ["QR code", "(in the real", "product)"];
// The illustrative QR image drawn in place of the placeholder lines.
export const QR_IMAGE_SOURCE = "/kaki-qr.svg";
export const QR_CAPTION = "Family can scan this code";
export const FOLLOW_UP_LINE =
  'KaKi Talkie will ask on Saturday: "Did you collect your voucher?"';

export interface BookingReceipt {
  title: string;
  subtitle: string;
  printedAt: string;
  bodyLines: string[];
  caseLabel: string;
  caseId: string;
  kakiLabel: string;
  kakiValue: string;
  qrLines: string[];
  qrCaption: string;
  followUp: string;
}

/** Format the print moment as the prototype does: "Sun, 20 Sept 2026, 01:56 pm". */
export function formatPrintedAt(printedAt: Date): string {
  const date = printedAt.toLocaleDateString("en-SG", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  const time = printedAt
    .toLocaleTimeString("en-SG", { hour: "2-digit", minute: "2-digit", hour12: true })
    .toLowerCase();
  return `${date}, ${time}`;
}

/**
 * Return the receipt for a booking turn, or null when the turn is not one.
 *
 * A turn without a `case_id` is any ordinary answer: it keeps the plain slip
 * rendering the simulator has always used, so this never changes how a
 * non-booking turn looks.
 */
export function buildBookingReceipt(
  response: TurnResponse,
  printedAt: Date = new Date(),
): BookingReceipt | null {
  if (!response.case_id) {
    return null;
  }
  return {
    title: RECEIPT_TITLE,
    subtitle: RECEIPT_SUBTITLE,
    printedAt: formatPrintedAt(printedAt),
    bodyLines: wrapReceipt(response.slip_text),
    caseLabel: RECEIPT_CASE_LABEL,
    caseId: response.case_id,
    kakiLabel: RECEIPT_KAKI_LABEL,
    kakiValue: RECEIPT_KAKI_VALUE,
    qrLines: QR_PLACEHOLDER_LINES,
    qrCaption: QR_CAPTION,
    followUp: FOLLOW_UP_LINE,
  };
}
