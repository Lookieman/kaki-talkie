// v1.0 | 21-Sep-2026 | WP6.8 thinking filler: played once per turn, never looped.

/**
 * The "Wait ah" thinking filler (WP6.8).
 *
 * A grounded turn takes several seconds, and silence reads as a dead kiosk to
 * someone standing in front of it. One short canned line covers the gap.
 *
 * Two properties are the whole point, and both are enforced here rather than
 * left to the caller:
 *
 * - it plays **once** per turn. A filler that repeats while the backend is
 *   slow turns reassurance into nagging, and an elderly user cannot tell a
 *   loop from a stuck machine;
 * - it **never blocks the turn**. A missing asset, a browser that refuses
 *   autoplay, or a decode failure resolves quietly. The answer arriving
 *   matters; the filler does not.
 *
 * The clip is a committed asset, captured once with macOS `say` and never
 * regenerated, following the WP3/WP4.2 fixture convention. Its exact wording
 * is recorded in `public/README.md`.
 */

export const FILLER_SOURCE = "/thinking-filler.wav";

/** Build an audio element; injectable so tests need no DOM audio support. */
export type AudioFactory = (source: string) => HTMLAudioElement;

const defaultFactory: AudioFactory = (source) => new Audio(source);

export class ThinkingFiller {
  private readonly factory: AudioFactory;
  private current: HTMLAudioElement | null = null;
  private playing = false;

  constructor(factory: AudioFactory = defaultFactory) {
    this.factory = factory;
  }

  /**
   * Start the filler unless it is already playing this turn.
   *
   * Returns true when this call started playback, false when it was ignored
   * because the filler was already sounding. Never rejects.
   */
  async play(): Promise<boolean> {
    if (this.playing) {
      return false;
    }
    this.playing = true;
    try {
      const audio = this.factory(FILLER_SOURCE);
      // Explicit: a loop would be the one failure mode this class exists to
      // prevent, so it is set rather than assumed to default false.
      audio.loop = false;
      this.current = audio;
      await audio.play();
      return true;
    } catch {
      // Autoplay refused, asset missing, or codec unsupported: the turn
      // continues in silence rather than failing.
      return false;
    }
  }

  /** Stop the filler and allow the next turn to play it again. */
  stop(): void {
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
}
