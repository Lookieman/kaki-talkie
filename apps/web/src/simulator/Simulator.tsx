// v1.3 | 05-Sep-2026 | Support identifier generation in insecure browser contexts.
// v1.2 | 04-Sep-2026 | Stabilise the recording controller used during cleanup.
// v1.1 | 04-Sep-2026 | Preserve release handling while microphone permission resolves.
// v1.0 | 04-Sep-2026 | Implement the WP1.3 browser simulator interaction.

"use client";

import { useCallback, useEffect, useRef, useState } from "react"; //v1.1
import type { PointerEvent } from "react"; //v1.1

import { submitTurn, TurnResponse } from "../api-client/device";
import { createIdentifier } from "./identifiers"; //v1.3
import { RecordingLimitController, RecordingStopReason } from "./recorder";
import { wrapReceipt } from "./receipt";
import { DeviceState, DEVICE_STATES } from "./states";

const DEVICE_ID = "web-simulator";
const PRINT_PREVIEW_MS = 650;

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

async function playListeningChime(): Promise<void> {
  const AudioContextClass = window.AudioContext;
  const context = new AudioContextClass();
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  oscillator.frequency.value = 660;
  gain.gain.setValueAtTime(0.0001, context.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.12, context.currentTime + 0.015);
  gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.12);
  oscillator.connect(gain);
  gain.connect(context.destination);
  oscillator.start();
  oscillator.stop(context.currentTime + 0.13);
  await wait(140);
  await context.close();
}

async function playReply(response: TurnResponse): Promise<void> {
  if (response.reply_audio) {
    const audio = new Audio(response.reply_audio);
    await audio.play();
    if (!audio.ended) {
      await new Promise<void>((resolve) => {
        audio.addEventListener("ended", () => resolve(), { once: true });
        audio.addEventListener("error", () => resolve(), { once: true });
      });
    }
    return;
  }
  if ("speechSynthesis" in window) {
    await new Promise<void>((resolve) => {
      const utterance = new SpeechSynthesisUtterance(response.reply_text);
      utterance.lang = response.language;
      utterance.addEventListener("end", () => resolve(), { once: true });
      utterance.addEventListener("error", () => resolve(), { once: true });
      window.speechSynthesis.speak(utterance);
    });
  }
}

export function Simulator() {
  const [deviceState, setDeviceState] = useState<DeviceState>("idle");
  const [response, setResponse] = useState<TurnResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sessionId = useRef(createIdentifier("session"));
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const mediaStream = useRef<MediaStream | null>(null);
  const recordedChunks = useRef<Blob[]>([]);
  const limitController = useRef(new RecordingLimitController());
  const mounted = useRef(true);
  const pointerHeld = useRef(false); //v1.1

  useEffect(() => {
    const recordingController = limitController.current; //v1.2
    return () => {
      mounted.current = false;
      recordingController.stop(); //v1.2
      mediaRecorder.current?.stop();
      mediaStream.current?.getTracks().forEach((track) => track.stop());
      window.speechSynthesis?.cancel();
    };
  }, []);

  const completeTurn = useCallback(async (audio: Blob) => {
    try {
      setDeviceState("thinking");
      const turnResponse = await submitTurn(audio, {
        deviceId: DEVICE_ID,
        sessionId: sessionId.current,
        turnId: createIdentifier("turn"),
      });
      if (!mounted.current) {
        return;
      }
      setResponse(turnResponse);
      setDeviceState("speaking");
      await playReply(turnResponse);
      if (!mounted.current) {
        return;
      }
      setDeviceState("printing");
      await wait(PRINT_PREVIEW_MS);
      if (mounted.current) {
        setDeviceState("idle");
      }
    } catch (caughtError) {
      if (mounted.current) {
        const message = caughtError instanceof Error ? caughtError.message : "The turn could not be completed.";
        setError(message);
        setDeviceState("idle");
      }
    }
  }, []);

  const finishRecording = useCallback((reason: RecordingStopReason) => {
    const recorder = mediaRecorder.current;
    if (!recorder || recorder.state === "inactive") {
      return;
    }
    if (reason !== "limit") {
      limitController.current.stop();
    }
    recorder.stop();
  }, []);

  const beginRecording = useCallback(async () => {
    if (deviceState !== "idle") {
      return;
    }
    setError(null);
    setResponse(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mounted.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      mediaStream.current = stream;
      recordedChunks.current = [];
      const recorder = new MediaRecorder(stream);
      mediaRecorder.current = recorder;
      recorder.addEventListener("dataavailable", (event) => {
        if (event.data.size > 0) {
          recordedChunks.current.push(event.data);
        }
      });
      recorder.addEventListener(
        "stop",
        () => {
          const audio = new Blob(recordedChunks.current, { type: recorder.mimeType || "audio/webm" });
          stream.getTracks().forEach((track) => track.stop());
          mediaStream.current = null;
          mediaRecorder.current = null;
          void completeTurn(audio);
        },
        { once: true },
      );
      setDeviceState("listening");
      recorder.start(); //v1.1
      limitController.current.start(() => finishRecording("limit")); //v1.1
      void playListeningChime().catch(() => undefined); //v1.1
      if (!pointerHeld.current) { //v1.1
        finishRecording("release"); //v1.1
      }
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "Microphone access is unavailable.";
      setError(message);
      setDeviceState("idle");
    }
  }, [completeTurn, deviceState, finishRecording]);

  function handlePointerDown(event: PointerEvent<HTMLButtonElement>): void {
    pointerHeld.current = true; //v1.1
    event.currentTarget.setPointerCapture(event.pointerId);
    void beginRecording();
  }

  function handlePointerUp(): void {
    pointerHeld.current = false; //v1.1
    finishRecording("release");
  }

  const receiptLines = response?.slip_text ? wrapReceipt(response.slip_text) : [];

  return (
    <main className="simulator-shell">
      <section className="intro" aria-labelledby="simulator-title">
        <p className="eyebrow">Browser contract twin</p>
        <h1 id="simulator-title">KaKi-Talkie</h1>
        <p>Hold the button while speaking. Recording ends on release or automatically after 15 seconds.</p>
      </section>

      <section className="device" aria-label="KaKi-Talkie simulator">
        <ol className="state-track" aria-label="Device state">
          {DEVICE_STATES.map((state) => (
            <li key={state} className={state === deviceState ? "active" : ""} aria-current={state === deviceState ? "step" : undefined}>
              <span aria-hidden="true" />
              {state}
            </li>
          ))}
        </ol>

        <div className="display" aria-label="Device display" aria-live="polite">
          {response?.display_text || (deviceState === "listening" ? "Listening…" : "Ready when you are.")}
        </div>

        <button
          className="talk-button"
          type="button"
          disabled={deviceState !== "idle" && deviceState !== "listening"} //v1.1
          onPointerDown={handlePointerDown}
          onPointerUp={handlePointerUp}
          onPointerCancel={() => { //v1.1
            pointerHeld.current = false; //v1.1
            finishRecording("cancel"); //v1.1
          }}
          onContextMenu={(event) => event.preventDefault()}
          aria-label="Hold to talk"
        >
          <span>Hold to talk</span>
          <small>15 seconds maximum</small>
        </button>

        {error ? <p className="error" role="alert">{error}</p> : null}
      </section>

      <aside className={`receipt ${receiptLines.length ? "printed" : ""}`} aria-label="58 millimetre receipt preview">
        <p className="receipt-label">58 mm receipt</p>
        <div className="receipt-paper" aria-live="polite">
          {receiptLines.length ? receiptLines.map((line, index) => <div key={`${index}-${line}`}>{line || "\u00a0"}</div>) : <p>Your English slip will appear here.</p>}
        </div>
      </aside>
    </main>
  );
}
