# ADR 001: STT engine for the MVP

```text
+------------+--------------------------------------------------+
| Field      | Value                                            |
+------------+--------------------------------------------------+
| Date       | 14-Sep-2026                                      |
| Status     | Accepted                                         |
| Owner      | Luqman                                           |
| Acceptance | WP5-AT-08                                        |
+------------+--------------------------------------------------+
```

## Context

WP5.2 asked one question: should MERaLiON-3-3B-ASR replace Whisper
large-v3-turbo as the MVP speech-to-text engine?

MERaLiON is the Singapore-specific challenger named in `design.md` 6.1.
Its published coverage includes Singapore English, Malay, Hokkien and
natural code-switching. `execution-plan.md` v1.10 scoped WP5.2 as a
timeboxed viability check rather than a benchmark.

## What we tested

Four WP5.1 demo clips, one speaker, owner voice:

```text
+--------------------+------------------------------------------+
| Clip               | Content                                  |
+--------------------+------------------------------------------+
| en_sg_cdc          | Singlish, CDC Vouchers                   |
| ms_cdc             | Malay, CDC Vouchers                      |
| ms_codeswitch      | Malay-English, CareShield Life           |
| ms_unsupported     | Malay, out of scope (weather)            |
+--------------------+------------------------------------------+
```

Both engines transcribed the same files. MERaLiON also ran live in the
browser simulator through a sidecar on port 8083 that mirrors the
whisper-server `/inference` protocol, selected by pointing
`KAKI_WHISPER_URL` at the sidecar.

This is a demo sample, not a measured corpus. One voice, four clips. It
says nothing about other speakers, ages, accents or recording
conditions, and no conclusion below should be read as a quality
measurement.

## What we found

**MERaLiON transcribed all four clips faithfully.** On the code-switch
clip it kept the English product name intact inside a Malay sentence.
On the Singlish clip it preserved the spoken form where Whisper
normalised it toward standard English.

**Whisper transcribed them correctly too, through the application
path.** An early spike appeared to show Whisper translating Malay into
English and inventing text on the out-of-scope clip. That was a
test-rig fault: the standalone `whisper-server` was started without
`-l`, whose default is `en`. The application adapter already sends
`language=auto` and `response_format=verbose_json`, so the pipeline was
never affected. The WP5.1 tier B evidence confirms it, with language
evidence `malay` at probability 0.77 on the Malay clip.

**MERaLiON supplies no language evidence.** The `AutoProcessor` route
returns a decoded transcript string and nothing else. No language
field, no probability. The reply-language policy in
`orchestration/language_policy.py` uses Whisper's evidence as a
tie-breaker, and the WP5.1 gate depends on it.

**Latency, measured unequally:**

```text
+-----------+------------------+--------------------------------+
| Engine    | Per clip         | How measured                   |
+-----------+------------------+--------------------------------+
| Whisper   | ~0.5 s           | Warm HTTP server               |
| MERaLiON  | ~1.5 - 2.2 s     | In-process, cold generate, MPS |
+-----------+------------------+--------------------------------+
```

The comparison favours Whisper by construction. The order of magnitude
is still useful: MERaLiON is roughly three to four times slower on this
host.

**Adoption cost.** A production switch would need an adapter behind the
STT port, a fourth process on a fourth port, a virtual environment
pinned to `transformers` 4.50.1, and a replacement source of language
evidence.

## Decision

**Keep Whisper large-v3-turbo as the MVP baseline. Postpone MERaLiON
and revisit after WP6.**

MERaLiON is the better transcriber on this sample, but it is not the
better component. It arrives without the language evidence the pipeline
routes on, and adopting it before the pitch would trade a validated
path for an unbuilt adapter at three times the latency. Whisper already
answers the golden paths through the application pipeline, with Malay
retrieval scoring 0.73 to 0.81 via the English query rewrite. No
measured limitation justifies the switch inside the MVP window.

## Consequences

MERaLiON stays a live post-MVP candidate, not a closed question. The
finding that motivates a revisit is transcript fidelity on Singlish and
code-switch, which is real and reproducible.

Revisit when any of these hold:

- WP6 closes and there is time to build the adapter properly;
- Hokkien or Mandarin enters scope, where Whisper's coverage is the
  known limitation;
- the language-evidence gap has a design answer, whether a second
  detection step, a MERaLiON prompt that also returns a language
  label, or a policy that no longer needs STT evidence.

A future revisit should also test what this check could not: more than
one speaker, elderly and softer speech, and device-microphone audio
rather than browser recordings. It should measure MERaLiON warm and
served, not cold and in-process.

The sidecar at `~/src/spikes/meralion_sidecar.py` is a spike. It is not
part of the application, it is not gate evidence, and it should not be
committed to the repository. Raw comparison output is retained under
`$KAKI_DATA_ROOT/wp5.2/`.

## References

```text
+---------------------------------+------------------------------+
| Item                            | Location                     |
+---------------------------------+------------------------------+
| Raw comparison and transcripts  | $KAKI_DATA_ROOT/wp5.2/       |
| WP5.1 tier B evidence           | $KAKI_DATA_ROOT/wp5.1/       |
| Unit scope and timebox          | execution-plan.md 6          |
| MERaLiON install notes          | setup.md 7.3, 8.7            |
| Language policy rules           | wp-validation-runbook.md 10  |
+---------------------------------+------------------------------+
```
