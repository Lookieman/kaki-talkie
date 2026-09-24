// v1.1 | 24-Sep-2026 | WP6.8 voice revision: the second clip after a delay, never after stop.
// v1.0 | 21-Sep-2026 | WP6.8 thinking filler: once per turn, never looping, never fatal.

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_SECOND_DELAY_MS,
  FILLER_SOURCE,
  SECOND_FILLER_SOURCE,
  ThinkingFiller,
} from "../simulator/filler";

function fakeAudio(play: () => Promise<void> = async () => {}) {
  return {
    loop: true, // starts wrong on purpose: the filler must set it false
    currentTime: 5,
    play: vi.fn().mockImplementation(play),
    pause: vi.fn(),
  } as unknown as HTMLAudioElement;
}

describe("ThinkingFiller", () => {
  it("plays the committed clip once and never loops it", async () => {
    const audio = fakeAudio();
    const filler = new ThinkingFiller(() => audio);

    expect(await filler.play()).toBe(true);
    expect(audio.play).toHaveBeenCalledOnce();
    expect(audio.loop).toBe(false);
  });

  it("requests the committed asset path", async () => {
    const factory = vi.fn().mockReturnValue(fakeAudio());
    await new ThinkingFiller(factory).play();
    expect(factory).toHaveBeenCalledWith(FILLER_SOURCE);
  });

  it("ignores a second play while the first is still sounding", async () => {
    const audio = fakeAudio();
    const filler = new ThinkingFiller(() => audio);

    expect(await filler.play()).toBe(true);
    expect(await filler.play()).toBe(false);
    expect(await filler.play()).toBe(false);
    expect(audio.play).toHaveBeenCalledOnce();
  });

  it("plays again on the next turn once stopped", async () => {
    const audio = fakeAudio();
    const filler = new ThinkingFiller(() => audio);

    await filler.play();
    filler.stop();
    expect(await filler.play()).toBe(true);
    expect(audio.play).toHaveBeenCalledTimes(2);
  });

  it("stop rewinds the clip so the next turn starts at the beginning", async () => {
    const audio = fakeAudio();
    const filler = new ThinkingFiller(() => audio);

    await filler.play();
    filler.stop();
    expect(audio.pause).toHaveBeenCalledOnce();
    expect(audio.currentTime).toBe(0);
  });

  // The turn must survive a refused autoplay or a missing asset.
  it("never rejects when playback fails", async () => {
    const filler = new ThinkingFiller(() =>
      fakeAudio(async () => {
        throw new Error("autoplay blocked");
      }),
    );

    await expect(filler.play()).resolves.toBe(false);
  });

  it("stop is safe before anything has played", () => {
    expect(() => new ThinkingFiller(() => fakeAudio()).stop()).not.toThrow();
  });
});

describe("ThinkingFiller second stage", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  function recordingFactory() {
    const sources: string[] = [];
    const clips: HTMLAudioElement[] = [];
    const factory = (source: string) => {
      sources.push(source);
      const audio = fakeAudio();
      clips.push(audio);
      return audio;
    };
    return { factory, sources, clips };
  }

  it("defaults to a five-second delay", () => {
    expect(DEFAULT_SECOND_DELAY_MS).toBe(5000);
  });

  it("plays only the first clip when the answer is fast", async () => {
    vi.useFakeTimers();
    const { factory, sources } = recordingFactory();
    const filler = new ThinkingFiller(factory, 5000);

    await filler.play();
    await vi.advanceTimersByTimeAsync(1000);
    filler.stop(); // the answer arrived
    await vi.advanceTimersByTimeAsync(10000);

    expect(sources).toEqual([FILLER_SOURCE]);
  });

  it("plays the second clip once when the answer is slow", async () => {
    vi.useFakeTimers();
    const { factory, sources, clips } = recordingFactory();
    const filler = new ThinkingFiller(factory, 5000);

    await filler.play();
    await vi.advanceTimersByTimeAsync(5000);
    await vi.advanceTimersByTimeAsync(10000);

    expect(sources).toEqual([FILLER_SOURCE, SECOND_FILLER_SOURCE]);
    expect(clips[1].loop).toBe(false);
    expect(clips[0].pause).toHaveBeenCalled(); // never two clips at once
  });

  it("stop cuts the second clip and nothing plays afterwards", async () => {
    vi.useFakeTimers();
    const { factory, sources, clips } = recordingFactory();
    const filler = new ThinkingFiller(factory, 100);

    await filler.play();
    await vi.advanceTimersByTimeAsync(100);
    filler.stop();
    await vi.advanceTimersByTimeAsync(10000);

    expect(sources).toEqual([FILLER_SOURCE, SECOND_FILLER_SOURCE]);
    expect(clips[1].pause).toHaveBeenCalled();
  });

  it("a missing first clip still lets the second play, and never rejects", async () => {
    vi.useFakeTimers();
    const sources: string[] = [];
    const filler = new ThinkingFiller((source) => {
      sources.push(source);
      return fakeAudio(async () => {
        if (source === FILLER_SOURCE) {
          throw new Error("404");
        }
      });
    }, 100);

    await expect(filler.play()).resolves.toBe(false);
    await vi.advanceTimersByTimeAsync(100);
    expect(sources).toEqual([FILLER_SOURCE, SECOND_FILLER_SOURCE]);
  });
});
