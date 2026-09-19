// v1.0 | 18-Sep-2026 | WP6.6 demo admin page: language toggle, one push, status line.

"use client";

/**
 * The demo admin surface (design.md 5.5): four large buttons and a status
 * line, usable one-handed on a phone. Served by the simulator origin behind
 * the same human Access session as /sim; every backend call also carries the
 * application's own bearer token, asked for once and kept for the tab's
 * session. Every write names its device_id explicitly — the target comes
 * from the backend's configured default and is shown in the status line, so
 * the operator always knows which surface they are steering.
 */

import { useCallback, useEffect, useRef, useState } from "react";

const STATE_POLL_MS = 3000;
const TOKEN_KEY = "kaki-admin-token";

interface MessageState {
  message_key: string;
  state: string;
  target_device_id: string | null;
  pushed_at: string | null;
  delivered_at: string | null;
  delivered_count: number;
}

interface AdminState {
  default_device: string;
  config: { device_id: string; reply_language: string }[];
  messages: MessageState[];
}

function readToken(): string {
  const stored = window.sessionStorage.getItem(TOKEN_KEY);
  if (stored) {
    return stored;
  }
  const entered = window.prompt("Admin token (KAKI_ADMIN_TOKEN)") ?? "";
  if (entered.trim()) {
    window.sessionStorage.setItem(TOKEN_KEY, entered.trim());
  }
  return entered.trim();
}

export default function AdminPage() {
  const [token, setToken] = useState("");
  const [state, setState] = useState<AdminState | null>(null);
  const [status, setStatus] = useState("Connecting...");
  const busy = useRef(false);

  const call = useCallback(
    async (path: string, body?: object): Promise<Response> => {
      return fetch(path, {
        method: body ? "POST" : "GET",
        headers: {
          Authorization: `Bearer ${token}`,
          ...(body ? { "Content-Type": "application/json" } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
      });
    },
    [token],
  );

  const refresh = useCallback(async () => {
    if (!token) {
      return;
    }
    try {
      const response = await call("/api/admin/state");
      if (response.status === 401 || response.status === 403) {
        window.sessionStorage.removeItem(TOKEN_KEY);
        setStatus("Token rejected. Reload the page and enter it again.");
        return;
      }
      const body = (await response.json()) as AdminState;
      setState(body);
      const config = body.config.find((row) => row.device_id === body.default_device);
      const message = body.messages[0];
      setStatus(
        `Target ${body.default_device} · language ${config?.reply_language ?? "auto"} · ` +
          `push ${message ? `${message.state} (delivered ${message.delivered_count}x)` : "none"}`,
      );
    } catch {
      setStatus("Backend unreachable. Retrying...");
    }
  }, [call, token]);

  useEffect(() => {
    setToken(readToken());
  }, []);

  useEffect(() => {
    if (!token) {
      setStatus("No token entered. Reload the page to try again.");
      return;
    }
    void refresh();
    const interval = window.setInterval(() => void refresh(), STATE_POLL_MS);
    return () => window.clearInterval(interval);
  }, [refresh, token]);

  async function act(label: string, path: string, body: object): Promise<void> {
    if (busy.current || !state) {
      return;
    }
    busy.current = true;
    setStatus(`${label}...`);
    try {
      const response = await call(path, body);
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        setStatus(`${label} failed: HTTP ${response.status}` +
          (detail && "detail" in detail ? ` (${String(detail.detail)})` : ""));
        return;
      }
      await refresh();
    } catch {
      setStatus(`${label} failed: backend unreachable.`);
    } finally {
      busy.current = false;
    }
  }

  const target = state?.default_device ?? "...";

  function setLanguage(language: string): void {
    void act(`Set ${language.toUpperCase()}`, "/api/admin/config", {
      device_id: target,
      reply_language: language,
    });
  }

  return (
    <main className="admin-shell">
      <h1>KaKi-Talkie demo admin</h1>
      <p className="admin-status" role="status">{status}</p>
      <div className="admin-buttons">
        <button type="button" onClick={() => setLanguage("en")} disabled={!state}>
          English
        </button>
        <button type="button" onClick={() => setLanguage("ms")} disabled={!state}>
          Bahasa Melayu
        </button>
        <button type="button" onClick={() => setLanguage("auto")} disabled={!state}>
          Auto
        </button>
        <button
          type="button"
          className="admin-push"
          disabled={!state}
          onClick={() =>
            void act("Push", "/api/admin/push", { device_id: target })
          }
        >
          Push: CDC vouchers
        </button>
      </div>
      <style>{`
        .admin-shell {
          max-width: 28rem;
          margin: 0 auto;
          padding: 1.5rem 1rem 3rem;
          font-family: system-ui, sans-serif;
        }
        .admin-shell h1 {
          font-size: 1.4rem;
        }
        .admin-status {
          min-height: 3rem;
          font-size: 1.05rem;
          color: #333;
        }
        .admin-buttons {
          display: grid;
          gap: 1rem;
        }
        .admin-buttons button {
          font-size: 1.5rem;
          padding: 1.4rem 1rem;
          border-radius: 1rem;
          border: 2px solid #1d3557;
          background: #f1faee;
          color: #1d3557;
        }
        .admin-buttons button:disabled {
          opacity: 0.5;
        }
        .admin-push {
          background: #1d3557 !important;
          color: #f1faee !important;
        }
      `}</style>
    </main>
  );
}
