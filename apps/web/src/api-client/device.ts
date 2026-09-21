// v1.2 | 21-Sep-2026 | WP6.4 fix: carry the device bearer token on every device call.
// v1.1 | 18-Sep-2026 | WP6.6: fetch due nudges from the existing pending endpoint.
// v1.0 | 04-Sep-2026 | Call the shared multipart device-turn contract.

/**
 * WP6.4 put `require_device_token` on every `/api/device/*` route, so a call
 * without a bearer token is refused with 401 before the turn is processed.
 * The simulator is a device client and must carry the same shared secret the
 * Pi reads from /etc/kaki/device.toml.
 *
 * The token lives in localStorage under the same guarded pattern the admin
 * page uses: the operator enters it once per browser rather than once per
 * tab, so a reload mid-pitch does not stop to ask. A private window or
 * blocked site data makes every storage call throw, so each one is guarded
 * and the simulator falls back to prompting each time. It still works; it
 * just cannot remember.
 */

export type TurnState = "answered" | "refused" | "handed_off" | "acted" | "failed";

export interface SourceRecord {
  source_url: string;
  page_title: string;
  captured_at: string;
  source_updated_at: string | null;
  content_hash: string | null;
}

export interface TurnResponse {
  turn_id: string;
  reply_audio: string | null;
  reply_text: string;
  display_text: string;
  slip_text: string;
  language: string;
  state: TurnState;
  case_id: string | null;
  sources: SourceRecord[];
}

export interface TurnIdentity {
  deviceId: string;
  sessionId: string;
  turnId: string;
}

const TOKEN_KEY = "kaki-device-token";

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

/** Forget a rejected token, so the next call asks for it again. */
export function clearDeviceToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Nothing was stored, so nothing needs clearing.
  }
}

/**
 * Read the stored device token, or ask for it and store it.
 *
 * Returns "" when there is no window (server render) or the operator
 * dismisses the prompt; the caller still sends the request, and the backend's
 * 401 is surfaced as a readable error rather than a silent failure.
 */
export function readDeviceToken(): string {
  if (typeof window === "undefined") {
    return "";
  }
  const stored = readStored();
  if (stored) {
    return stored;
  }
  const entered = (window.prompt("Device token (KAKI_DEVICE_TOKEN)") ?? "").trim();
  if (entered) {
    writeStored(entered);
  }
  return entered;
}

/** Build the bearer header, omitting it entirely when no token is known. */
function authorization(): Record<string, string> {
  const token = readDeviceToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function submitTurn(
  audio: Blob,
  identity: TurnIdentity,
  signal?: AbortSignal,
): Promise<TurnResponse> {
  const form = new FormData();
  form.set("audio", audio, "browser-recording.webm");
  form.set("device_id", identity.deviceId);
  form.set("session_id", identity.sessionId);
  form.set("turn_id", identity.turnId);

  const response = await fetch("/api/device/turn", {
    method: "POST",
    headers: authorization(),
    body: form,
    signal,
  });
  if (!response.ok) {
    // A refused token is forgotten, so the next turn asks for it again
    // instead of failing identically forever (WP6.4).
    if (response.status === 401 || response.status === 403) {
      clearDeviceToken();
    }
    throw new Error(`Turn request failed with HTTP ${response.status}.`);
  }
  return (await response.json()) as TurnResponse;
}

export async function fetchPending(
  deviceId: string,
  signal?: AbortSignal,
): Promise<unknown> {
  // The existing WP1 path; WP6.6 adds only the device identity, so the
  // backend can mark this device's nudges delivered as they leave.
  const response = await fetch(
    `/api/device/pending?device_id=${encodeURIComponent(deviceId)}`,
    { headers: authorization(), signal },
  );
  if (!response.ok) {
    throw new Error(`Pending request failed with HTTP ${response.status}.`);
  }
  return (await response.json()) as unknown;
}
