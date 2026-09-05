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
});
