// v1.0 | 24-Sep-2026 | Pitch receipt page: the projector view, apart from its polling.

import { useLayoutEffect, useRef } from "react";

import { BookingReceiptSlip } from "./BookingReceiptSlip";
import type { BookingReceipt } from "./bookingReceipt";

/**
 * Draw the /receipt projector screen: the booking slip, or a waiting line.
 *
 * Kept free of polling and auth so the layout can be rendered and checked on
 * its own at projector sizes. The slip is the simulator's own component,
 * scaled up whole so its proportions hold: `fitToViewport` measures it at
 * 1x and zooms it to fill 94% of the screen in both directions, capped at
 * 2.2x, so the whole slip is visible at 1280x720 and 1920x1080 alike.
 */

const FILL = 0.94;
const MAX_ZOOM = 2.2;

/** Zoom `paper` so its unscaled box fills the viewport without overflowing it. */
export function fitToViewport(paper: HTMLElement): void {
  paper.style.zoom = "1";
  const box = paper.getBoundingClientRect();
  if (box.width <= 0 || box.height <= 0) {
    return;
  }
  const zoom = Math.min(
    MAX_ZOOM,
    (window.innerWidth * FILL) / box.width,
    (window.innerHeight * FILL) / box.height,
  );
  paper.style.zoom = String(Math.max(zoom, 0.5));
}
export function ReceiptProjector(
  { receipt, message }: { receipt: BookingReceipt | null; message: string },
) {
  const paper = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const element = paper.current;
    if (!element) {
      return;
    }
    const fit = () => fitToViewport(element);
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, [receipt]);

  return (
    <main className="receipt-projector">
      {receipt ? (
        <div className="receipt-paper" aria-live="polite" ref={paper}>
          <BookingReceiptSlip receipt={receipt} />
        </div>
      ) : (
        <p className="receipt-waiting" role="status">
          {message}
        </p>
      )}
      <style>{`
        .receipt-projector {
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 2vh 2vw;
          box-sizing: border-box;
          background: #1f2430;
        }
        /* The paper's zoom is set by fitToViewport. Nothing here clips:
           if a fit ever fails, the page scrolls instead. */
        .receipt-waiting {
          color: #f1faee;
          font-family: system-ui, sans-serif;
          font-size: clamp(2rem, 5vw, 4rem);
          text-align: center;
        }
      `}</style>
    </main>
  );
}
