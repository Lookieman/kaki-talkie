// v1.1 | 24-Sep-2026 | WP6.8 voice revision: two-stage filler, the second clip after a delay.
// v1.0 | 21-Sep-2026 | WP6.8 thinking filler: played once per turn, never looped.

/**
 * The two-stage thinking filler (WP6.8 voice revision).
 *
 * A grounded turn takes several seconds, and silence reads as a dead kiosk to
 * someone standing in front of it. Two short canned lines cover the gap:
 *
 * 1. the first clip plays once, the moment the thinking state starts;
 * 2. the second plays once, only if the answer is still missing
 *    `secondDelayMs` after that (default 5 s, matching the Pi's
 *    `filler_second_delay_seconds`).
 *
 * Three properties are the whole point, and all are enforced here rather
 * than left to the caller:
 *
 * - each clip plays **once** per turn and never loops. A filler that repeats
 *   turns reassurance into nagging, and an elderly user cannot tell a loop
 *   from a stuck machine;
 * - **nothing plays after `stop()`**, which the caller invokes the moment the
 *   answer arrives. It cuts a sounding clip and cancels the pending one;
 * - it **never blocks the turn**. A missing asset, a browser that refuses
 *   autoplay, or a decode failure resolves quietly.
 *
 * The clips are committed assets recorded with ElevenLabs; the Pi plays the
 * same recordings. `public/README.md` records the file names and wording.
 */

export const FILLER_SOURCE = "/thinking-filler-1.wav";
export const SECOND_FILLER_SOURCE = "/thinking-filler-2.wav";
export const DEFAULT_SECOND_DELAY_MS = 5000;

/** What each clip says; the Pi's `thinking_filler.py` holds the same text. */
export const FILLER_TEXTS = [
  "Wait ah, I check for you.",
  "Almost there ah, Auntie. Wait a bit more.",
] as const;

/** Build an audio element; injectable so tests need no DOM audio support. */
export type AudioFactory = (source: string) => HTMLAudioElement;

const defaultFactory: AudioFactory = (source) => new Audio(source);

export class ThinkingFiller {
  private readonly factory: AudioFactory;
  private readonly secondDelayMs: number;
  private current: HTMLAudioElement | null = null;
  private secondTimer: ReturnType<typeof setTimeout> | null = null;
  private playing = false;

  constructor(factory: AudioFactory = defaultFactory, secondDelayMs = DEFAULT_SECOND_DELAY_MS) {
    this.factory = factory;
    this.secondDelayMs = secondDelayMs;
  }

  /**
   * Start the filler for this turn unless it is already running.
   *
   * Plays the first clip at once and schedules the second. Returns true when
   * the first clip started, false when the call was ignored or the first clip
   * could not play (the second is still scheduled). Never rejects.
   */
  async play(): Promise<boolean> {
    if (this.playing) {
      return false;
    }
    this.playing = true;
    this.secondTimer = setTimeout(() => {
      this.secondTimer = null;
      void this.playClip(SECOND_FILLER_SOURCE);
    }, this.secondDelayMs);
    return this.playClip(FILLER_SOURCE);
  }

  /** Stop the filler, cancel the second clip, and allow the next turn to play again. */
  stop(): void {
    if (this.secondTimer !== null) {
      clearTimeout(this.secondTimer);
      this.secondTimer = null;
    }
    const audio = this.current;
    this.current = null;
    this.playing = false;
    if (!audio) {
      return;
    }
    try {
      audio.pause();
      audio.currentTime = 0;
    } catch {
      // A element that never began playing has nothing to stop.
    }
  }

  private async playClip(source: string): Promise<boolean> {
    if (!this.playing) {
      return false; // stopped before this clip's turn came
    }
    try {
      const previous = this.current;
      const audio = this.factory(source);
      // Explicit: a loop would be the one failure mode this class exists to
      // prevent, so it is set rather than assumed to default false.
      audio.loop = false;
      this.current = audio;
      previous?.pause(); // never two filler clips at once
      await audio.play();
      if (!this.playing || this.current !== audio) {
        // The answer arrived while play() was pending: stay silent.
        audio.pause();
        return false;
      }
      return true;
    } catch {
      // Autoplay refused, asset missing, or codec unsupported: the turn
      // continues in silence rather than failing.
      return false;
    }
  }
}
