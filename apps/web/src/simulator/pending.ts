// v1.0 | 18-Sep-2026 | WP6.6: poll the pending endpoint and hand each nudge over once.
//
// The simulator learns of an admin push through the existing
// GET /api/device/pending — no new request path (design.md 5.5). The backend
// already delivers each push at most once per device; the tracker here is the
// client's own second guard, so a nudge is surfaced once even if a response
// is processed twice (a re-render, an overlapping poll).

export const PENDING_POLL_SECONDS = 3;

export interface PendingNudge {
  id: string;
  kind: string;
  text: string;
  language: string;
  audio: string | null;
  pushed_at: string | null;
}

/**
 * Keep the deliveries already surfaced, so a nudge never replays locally.
 *
 * The key is id plus pushed_at: a re-pushed rehearsal of the same seeded
 * message carries a new pushed_at and surfaces again, while a duplicate
 * processing of one delivery does not.
 */
export class NudgeTracker {
  private readonly seen = new Set<string>();

  /** Return the not-yet-surfaced nudges, recording them as surfaced. */
  takeNew(items: PendingNudge[]): PendingNudge[] {
    const fresh: PendingNudge[] = [];
    for (const item of items) {
      const key = `${item.id}@${item.pushed_at ?? ""}`;
      if (!this.seen.has(key)) {
        this.seen.add(key);
        fresh.push(item);
      }
    }
    return fresh;
  }

  /** Allow a repeated push of the same seeded message to surface again. */
  reset(): void {
    this.seen.clear();
  }
}

/** Keep only well-formed nudge items; the device never trusts a shape blindly. */
export function parsePendingItems(payload: unknown): PendingNudge[] {
  if (!Array.isArray(payload)) {
    return [];
  }
  const items: PendingNudge[] = [];
  for (const entry of payload) {
    if (
      typeof entry === "object" && entry !== null &&
      typeof (entry as PendingNudge).id === "string" &&
      typeof (entry as PendingNudge).text === "string"
    ) {
      const item = entry as PendingNudge;
      items.push({
        id: item.id,
        kind: typeof item.kind === "string" ? item.kind : "nudge",
        text: item.text,
        language: typeof item.language === "string" ? item.language : "en",
        audio: typeof item.audio === "string" ? item.audio : null,
        pushed_at: typeof item.pushed_at === "string" ? item.pushed_at : null,
      });
    }
  }
  return items;
}
