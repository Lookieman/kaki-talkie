// v1.0 | 04-Sep-2026 | Call the shared multipart device-turn contract.

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
    body: form,
    signal,
  });
  if (!response.ok) {
    throw new Error(`Turn request failed with HTTP ${response.status}.`);
  }
  return (await response.json()) as TurnResponse;
}
