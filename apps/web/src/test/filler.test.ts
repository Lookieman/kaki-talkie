// v1.0 | 21-Sep-2026 | WP6.8 thinking filler: once per turn, never looping, never fatal.

import { describe, expect, it, vi } from "vitest";

import { FILLER_SOURCE, ThinkingFiller } from "../simulator/filler";

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
