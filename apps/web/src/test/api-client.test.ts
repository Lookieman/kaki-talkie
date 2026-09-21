// v1.1 | 21-Sep-2026 | WP6.4 fix: the device bearer token rides every device call.
// v1.0 | 04-Sep-2026 | Verify the simulator uses the shared multipart turn contract.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearDeviceToken, fetchPending, submitTurn } from "../api-client/device";

/** Give the module a window with working localStorage and no prompt needed. */
function stubBrowser(token: string | null): { prompt: ReturnType<typeof vi.fn> } {
  const store = new Map<string, string>();
  if (token !== null) {
    store.set("kaki-device-token", token);
  }
  const prompt = vi.fn().mockReturnValue("prompted-token");
  vi.stubGlobal("window", {
    localStorage: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
      removeItem: (key: string) => void store.delete(key),
    },
    prompt,
  });
  return { prompt };
}

function turnPayload() {
  return {
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
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("submitTurn", () => {
  beforeEach(() => {
    stubBrowser("stored-device-token");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts audio and all mandatory identifiers as multipart form data", async () => {
    const payload = turnPayload();
    const fetchSpy = vi.fn().mockResolvedValue(jsonResponse(payload));
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

  // WP6.4: every /api/device/* route refuses a request without this header.
  it("sends the stored device token as a bearer header", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(jsonResponse(turnPayload()));
    vi.stubGlobal("fetch", fetchSpy);

    await submitTurn(new Blob(["audio"]), {
      deviceId: "simulator-device",
      sessionId: "session-1",
      turnId: "turn-1",
    });

    const [, options] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(options.headers).toEqual({ Authorization: "Bearer stored-device-token" });
  });

  it("asks for the token once when storage is empty, then stores it", async () => {
    const { prompt } = stubBrowser(null);
    // A fresh Response per call: a body can only be read once.
    const fetchSpy = vi.fn().mockImplementation(async () => jsonResponse(turnPayload()));
    vi.stubGlobal("fetch", fetchSpy);
    const identity = { deviceId: "d", sessionId: "s", turnId: "t" };

    await submitTurn(new Blob(["audio"]), identity);
    await submitTurn(new Blob(["audio"]), identity);

    expect(prompt).toHaveBeenCalledOnce();
    for (const call of fetchSpy.mock.calls) {
      const [, options] = call as [string, RequestInit];
      expect(options.headers).toEqual({ Authorization: "Bearer prompted-token" });
    }
  });

  it("forgets a refused token so the next turn asks again", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(jsonResponse({ detail: "no" }, 401));
    vi.stubGlobal("fetch", fetchSpy);

    await expect(
      submitTurn(new Blob(["audio"]), { deviceId: "d", sessionId: "s", turnId: "t" }),
    ).rejects.toThrow("HTTP 401");
    // The rejected token is gone, so the next call prompts rather than
    // repeating the same refused request forever.
    expect(window.localStorage.getItem("kaki-device-token")).toBeNull();
  });
});

describe("fetchPending", () => {
  beforeEach(() => {
    stubBrowser("stored-device-token");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends the device token and the device identity", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchSpy);

    await fetchPending("simulator-device");

    const [url, options] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/device/pending?device_id=simulator-device");
    expect(options.headers).toEqual({ Authorization: "Bearer stored-device-token" });
  });
});

describe("clearDeviceToken", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("survives storage that refuses every call", () => {
    vi.stubGlobal("window", {
      localStorage: {
        getItem: () => {
          throw new Error("blocked");
        },
        setItem: () => {
          throw new Error("blocked");
        },
        removeItem: () => {
          throw new Error("blocked");
        },
      },
      prompt: vi.fn().mockReturnValue(""),
    });

    expect(() => clearDeviceToken()).not.toThrow();
  });
});
