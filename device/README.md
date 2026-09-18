# kaki-device

The thin Raspberry Pi client. It records an utterance, posts it to the backend's
device contract, shows the answer and prints the slip. It decides nothing else.

Installation for the Pi is `docs/04-prototype/setup.md` section 29. Validation is
`docs/04-prototype/wp-validation-runbook.md` section 11.

## What it holds, and what it must not

The Pi holds no model, corpus, prompt, retrieval or case logic (design.md 3).
`scripts/wp_check.py --unit WP6.1 --tier A` reads this package statically and
fails on an unapproved import, dependency, request path, environment variable,
or on prompt, model-port or SQL text (WP6-AT-13). `device/tests/test_thin_client.py`
runs the same inspection, so CI catches a violation before the gate does.

Runtime dependencies are the standard library plus `httpx`. `pygame` is the
optional `display` extra, used only by the renderer.

## Modules

```text
config.py               TOML file plus KAKI_DEVICE_* overrides, validated at startup
api_client.py           POST /api/device/turn, GET /api/device/pending, GET /api/health
state_machine.py        The turn loop: idle, recording, thinking, answer, error
display/layout.py       Pure state-to-frame layout; no drawing, no pygame
display/pygame_backend  Fullscreen renderer; the only module that imports pygame
io_ports.py             Button, microphone, speaker, printer and display protocols
mock_io.py              Fakes for all five, so the whole loop runs on a Mac
main.py                 Entry point; --mock is the only mode until WP6.2
```

## Running it

```sh
python -m pip install -e device            # add [display] for a real window
python -m kaki_device.main --mock --headless --turns 1
python scripts/wp6_1_frames.py --fixture backend/src/kaki_backend/fixtures/cdc_question.wav
```

Real hardware ports arrive with WP6.2 (button, audio) and WP6.3 (printer);
without `--mock` the entry point says so and exits.

## Tests

```sh
python -m unittest discover -s device/tests -t device/tests
```

They need no hardware, no screen, no network and no backend.
