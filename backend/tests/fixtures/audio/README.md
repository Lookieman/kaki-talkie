# WP2.1 audio fixtures

`chrome-tone.webm` was captured on 06-Sep-2026 using the installed Windows
Google Chrome 152 (headless), not a media encoder impersonating browser output.
The exact user agent and MIME type are in `chrome-tone.json`.

Capture used an AudioContext at 48000 Hz, a 440 Hz oscillator with gain 0.2,
and a MediaStreamAudioDestinationNode. MediaRecorder used its default format,
recorded for a requested 1000 ms, then emitted WebM/Opus. No microphone,
personal speech or network recording was involved. This tests Chrome's encoder
and container, not physical microphone capture or Mac browser interaction.

Expected decoded duration: approximately 1 second, tolerance 0.1 seconds.
Expected normalised output: 16000 Hz, mono, signed 16-bit PCM WAV, non-silent.
Other fixtures are constructed in memory by deterministic tests.
