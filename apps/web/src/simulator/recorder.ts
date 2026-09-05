// v1.0 | 04-Sep-2026 | Enforce the browser recording duration boundary.

export const MAX_RECORDING_MS = 15_000;

export type RecordingStopReason = "release" | "limit" | "cancel";
export type ScheduleTimeout = (callback: () => void, delayMs: number) => ReturnType<typeof setTimeout>;
export type CancelTimeout = (handle: ReturnType<typeof setTimeout>) => void;

export class RecordingLimitController {
  private timeoutHandle: ReturnType<typeof setTimeout> | null = null;
  private recording = false;

  constructor(
    private readonly schedule: ScheduleTimeout = setTimeout,
    private readonly cancel: CancelTimeout = clearTimeout,
  ) {}

  start(onLimit: () => void): void {
    if (this.recording) {
      return;
    }
    this.recording = true;
    this.timeoutHandle = this.schedule(() => {
      this.recording = false;
      this.timeoutHandle = null;
      onLimit();
    }, MAX_RECORDING_MS);
  }

  stop(): boolean {
    if (!this.recording) {
      return false;
    }
    this.recording = false;
    if (this.timeoutHandle !== null) {
      this.cancel(this.timeoutHandle);
      this.timeoutHandle = null;
    }
    return true;
  }

  isRecording(): boolean {
    return this.recording;
  }
}
