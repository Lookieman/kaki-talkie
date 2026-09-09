// v1.1 | 09-Sep-2026 | Guard against detached-this calls into the browser timer APIs.
// v1.0 | 04-Sep-2026 | Verify the recording cap and release cancellation.

import { describe, expect, it, vi } from "vitest";

import { MAX_RECORDING_MS, RecordingLimitController } from "../simulator/recorder";

describe("RecordingLimitController", () => {
  it("stops recording automatically at exactly 15 seconds", () => {
    vi.useFakeTimers();
    const onLimit = vi.fn();
    const controller = new RecordingLimitController();

    controller.start(onLimit);
    vi.advanceTimersByTime(MAX_RECORDING_MS - 1);
    expect(onLimit).not.toHaveBeenCalled();
    expect(controller.isRecording()).toBe(true);

    vi.advanceTimersByTime(1);
    expect(onLimit).toHaveBeenCalledOnce();
    expect(controller.isRecording()).toBe(false);
    vi.useRealTimers();
  });

  it("cancels the cap when the user releases early", () => {
    vi.useFakeTimers();
    const onLimit = vi.fn();
    const controller = new RecordingLimitController();

    controller.start(onLimit);
    vi.advanceTimersByTime(3_000);
    expect(controller.stop()).toBe(true);
    vi.advanceTimersByTime(MAX_RECORDING_MS);

    expect(onLimit).not.toHaveBeenCalled();
    expect(controller.isRecording()).toBe(false);
    vi.useRealTimers();
  });

  it("never gives the timer globals a detached this receiver", () => { //v1.1
    // Chrome's window.setTimeout throws "Illegal invocation" when invoked with
    // any receiver other than the window or undefined. Node's timers do not,
    // so this test records the receiver instead of relying on the throw.
    const observedReceivers: unknown[] = [];
    const timerHandle = 0 as unknown as ReturnType<typeof setTimeout>;
    vi.stubGlobal("setTimeout", function (this: unknown) {
      observedReceivers.push(this);
      return timerHandle;
    });
    vi.stubGlobal("clearTimeout", function (this: unknown) {
      observedReceivers.push(this);
    });
    try {
      const controller = new RecordingLimitController();
      controller.start(() => undefined);
      controller.stop();
    } finally {
      vi.unstubAllGlobals();
    }

    expect(observedReceivers).toHaveLength(2);
    for (const receiver of observedReceivers) {
      expect(receiver === undefined || receiver === globalThis).toBe(true);
    }
  });
});
