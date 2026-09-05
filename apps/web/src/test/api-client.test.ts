// v1.0 | 04-Sep-2026 | Verify the simulator uses the shared multipart turn contract.

import { afterEach, describe, expect, it, vi } from "vitest";

import { submitTurn } from "../api-client/device";

describe("submitTurn", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts audio and all mandatory identifiers as multipart form data", async () => {
    const payload = {
      turn_id: "turn-1",
      reply_audio: null,
      reply_text: "Canned reply",
      display_text: "Display reply",
      slip_text: "English slip",
      language: "en",
      state: "answered",
      case_id: null,
      sources: [],
    };
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    const result = await submitTurn(new Blob(["audio"]), {
      deviceId: "simulator-device",
      sessionId: "session-1",
      turnId: "turn-1",
    });

    expect(result).toEqual(payload);
    expect(fetchSpy).toHaveBeenCalledOnce();
    const [url, options] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/device/turn");
    expect(options.method).toBe("POST");
    const form = options.body as FormData;
    expect(form.get("device_id")).toBe("simulator-device");
    expect(form.get("session_id")).toBe("session-1");
    expect(form.get("turn_id")).toBe("turn-1");
    expect(form.get("audio")).toBeInstanceOf(File);
  });
});
