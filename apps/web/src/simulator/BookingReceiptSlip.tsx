// v1.1 | 25-Sep-2026 | Draw the QR image in place of the dashed placeholder.
// v1.0 | 24-Sep-2026 | Extract the WP6.7 booking slip so /sim and /receipt draw the same one.

import { QR_IMAGE_SOURCE, type BookingReceipt } from "./bookingReceipt";

/**
 * Draw one booking receipt as the 58 mm slip (WP6-AT-20).
 *
 * Moved unchanged out of `Simulator.tsx` so the projector page at /receipt
 * renders the identical slip. Place it inside a `.receipt-paper` element,
 * which supplies the paper, font and spacing rules in `globals.css`.
 */
export function BookingReceiptSlip({ receipt }: { receipt: BookingReceipt }) {
  return (
    <div className="slip">
      <p className="slip-title">{receipt.title}</p>
      <p className="slip-subtitle">{receipt.subtitle}</p>
      <p className="slip-subtitle">{receipt.printedAt}</p>
      <hr />
      {receipt.bodyLines.map((line, index) => (
        <div key={`body-${index}-${line}`}>{line || " "}</div>
      ))}
      <hr />
      <p className="slip-field">
        <span>{receipt.caseLabel}</span>
        <span>{receipt.caseId}</span>
      </p>
      <p className="slip-field">
        <span>{receipt.kakiLabel}</span>
        <span>{receipt.kakiValue}</span>
      </p>
      {/* Printed illustration only: no case, no follow-up state. */}
      {/* eslint-disable-next-line @next/next/no-img-element -- a static SVG needs no optimisation */}
      <img className="slip-qr-image" src={QR_IMAGE_SOURCE} alt="QR code" width={140} height={140} />
      <p className="slip-caption">{receipt.qrCaption}</p>
      <p className="slip-followup">{receipt.followUp}</p>
    </div>
  );
}
