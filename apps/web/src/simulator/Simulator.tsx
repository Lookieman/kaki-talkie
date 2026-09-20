// v1.6 | 19-Sep-2026 | WP6.6: show the nudge inside the device frame and clear it on the next turn.
// v1.5 | 18-Sep-2026 | WP6.6: poll pending every 3 s while idle and play a nudge once.
// v1.4 | 13-Sep-2026 | Apply the client print policy and keep the last printed slip (WP4.2).
// v1.3 | 05-Sep-2026 | Support identifier generation in insecure browser contexts.
// v1.2 | 04-Sep-2026 | Stabilise the recording controller used during cleanup.
// v1.1 | 04-Sep-2026 | Preserve release handling while microphone permission resolves.
// v1.0 | 04-Sep-2026 | Implement the WP1.3 browser simulator interaction.

"use client";

import { useCallback, useEffect, useRef, useState } from "react"; //v1.1
import type { PointerEvent } from "react"; //v1.1

import { fetchPending, submitTurn, TurnResponse } from "../api-client/device"; //v1.5
import { createIdentifier } from "./identifiers"; //v1.3
import { RecordingLimitController, RecordingStopReason } from "./recorder";
import { DEFAULT_PRINT_POLICY, PRINT_POLICIES, PrintPolicy, shouldPrint } from "./printPolicy"; //v1.4
import { wrapReceipt } from "./receipt";
import { DeviceState, DEVICE_STATES } from "./states";
import { NudgeTracker, parsePendingItems, PENDING_POLL_SECONDS, PendingNudge } from "./pending"; //v1.5

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

async function playNudgeAudio(nudge: PendingNudge): Promise<void> { //v1.5
  if (nudge.audio) {
    const audio = new Audio(nudge.audio);
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
      const utterance = new SpeechSynthesisUtterance(nudge.text);
      utterance.lang = nudge.language;
      utterance.addEventListener("end", () => resolve(), { once: true });
      utterance.addEventListener("error", () => resolve(), { once: true });
      window.speechSynthesis.speak(utterance);
    });
  }
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
  const [printPolicy, setPrintPolicy] = useState<PrintPolicy>(DEFAULT_PRINT_POLICY); //v1.4
  const [printedSlip, setPrintedSlip] = useState(""); //v1.4
  const [nudge, setNudge] = useState<PendingNudge | null>(null); //v1.5
  const printPolicyRef = useRef<PrintPolicy>(DEFAULT_PRINT_POLICY); //v1.4
  const sessionId = useRef(createIdentifier("session"));
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const mediaStream = useRef<MediaStream | null>(null);
  const recordedChunks = useRef<Blob[]>([]);
  const limitController = useRef(new RecordingLimitController());
  const mounted = useRef(true);
  const pointerHeld = useRef(false); //v1.1
  const nudgeTracker = useRef(new NudgeTracker()); //v1.5
  const deviceStateRef = useRef<DeviceState>("idle"); //v1.5
  deviceStateRef.current = deviceState; //v1.5

  useEffect(() => { //v1.5
    // WP6.6: the admin push arrives through the existing pending endpoint.
    // Poll only while idle, so a nudge never interrupts a turn in progress,
    // and surface each delivery exactly once (NudgeTracker).
    const interval = window.setInterval(async () => {
      if (deviceStateRef.current !== "idle") {
        return;
      }
      try {
        const items = parsePendingItems(await fetchPending(DEVICE_ID));
        const fresh = nudgeTracker.current.takeNew(items);
        if (fresh.length > 0 && mounted.current) {
          setNudge(fresh[0]);
          await playNudgeAudio(fresh[0]);
        }
      } catch {
        // A failed poll is silent; the next tick tries again.
      }
    }, PENDING_POLL_SECONDS * 1000);
    return () => window.clearInterval(interval);
  }, []);

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
      if (!shouldPrint(printPolicyRef.current, turnResponse)) { //v1.4
        // A response that does not print leaves the last receipt in place.
        setDeviceState("idle");
        return;
      }
      setPrintedSlip(turnResponse.slip_text); //v1.4
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
    // An announcement belongs to the moment it arrived. Clear it as the next
    // turn starts, so it never sits over someone else's answer.
    setNudge(null); //v1.6
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

  function handlePrintPolicyChange(policy: PrintPolicy): void { //v1.4
    printPolicyRef.current = policy;
    setPrintPolicy(policy);
  }

  const receiptLines = printedSlip ? wrapReceipt(printedSlip) : []; //v1.4

  return (
    <main className="simulator-shell">
      <section className="intro" aria-labelledby="simulator-title">
        <p className="eyebrow">Browser contract twin</p>
        <h1 id="simulator-title">KaKi-Talkie</h1>
        <p>Hold the button while speaking. Recording ends on release or automatically after 15 seconds.</p>
      </section>

      <section className="device" aria-label="KaKi-Talkie simulator">
        {nudge ? ( //v1.6
          <section className="nudge" role="status" aria-label="Announcement">
            <p>{nudge.text}</p>
          </section>
        ) : null}

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
        <fieldset className="print-policy">
          <legend>Print policy</legend>
          {PRINT_POLICIES.map((policy) => (
            <label key={policy}>
              <input
                type="radio"
                name="print-policy"
                value={policy}
                checked={printPolicy === policy}
                onChange={() => handlePrintPolicyChange(policy)}
              />
              {policy}
            </label>
          ))}
        </fieldset>
        <div className="receipt-paper" aria-live="polite">
          {receiptLines.length ? receiptLines.map((line, index) => <div key={`${index}-${line}`}>{line || "\u00a0"}</div>) : <p>Your English slip will appear here.</p>}
        </div>
      </aside>
    </main>
  );
}
