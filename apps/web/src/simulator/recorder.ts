// v1.1 | 09-Sep-2026 | Call browser timer functions without a detached this receiver.
// v1.0 | 04-Sep-2026 | Enforce the browser recording duration boundary.

export const MAX_RECORDING_MS = 15_000;

export type RecordingStopReason = "release" | "limit" | "cancel";
export type ScheduleTimeout = (callback: () => void, delayMs: number) => ReturnType<typeof setTimeout>;
export type CancelTimeout = (handle: ReturnType<typeof setTimeout>) => void;

export class RecordingLimitController {
  private timeoutHandle: ReturnType<typeof setTimeout> | null = null;
  private recording = false;

  constructor(
    // Wrap the globals: storing them bare and invoking via `this.schedule(...)`
    // hands Chrome's native setTimeout this controller as `this`, which throws
    // "Illegal invocation". An unqualified call keeps the receiver legal.
    private readonly schedule: ScheduleTimeout = (callback, delayMs) => setTimeout(callback, delayMs), //v1.1
    private readonly cancel: CancelTimeout = (handle) => clearTimeout(handle), //v1.1
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
