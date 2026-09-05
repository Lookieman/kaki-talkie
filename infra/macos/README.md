# WP1.4 localhost deployment and owner gate

The design baseline is the Mac Mini, with FastAPI on `127.0.0.1:8000` and the web
application on `127.0.0.1:3000`. This unit adds no model services, database, launchd
installation, or hardware integration. Keep runtime data outside Git under
`KAKI_DATA_ROOT` (baseline `/Users/websvc/kaki-talkie-data`) when later packages need it.

## Install and start

Use Python 3.11 or newer and Node 22. From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e 'backend[test,dev]'
cd apps/web
npm ci
npm run build
```

Start two foreground processes in separate terminals. From the repository root
with the virtual environment active, start the backend:

```sh
python -m kaki_backend.main
```

From `apps/web`, start the production web application:

```sh
npm start
```

Both commands explicitly bind to loopback. Inspect listeners on the Mac:

```sh
lsof -nP -iTCP:8000 -sTCP:LISTEN
lsof -nP -iTCP:3000 -sTCP:LISTEN
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:3000/api/health
```

Both listeners must show `127.0.0.1`, never `*`, `0.0.0.0`, or a LAN address.
Both health requests must return `{"status":"ok","version":"0.1.0"}`.
Open `http://127.0.0.1:3000/sim` for local testing. Phone testing uses the protected
HTTPS hostname, not a LAN bind. Follow [Cloudflare setup and verification](../cloudflare/README.md).
Stop only these foreground services with Ctrl+C when finished.

## Tier A commands

Run these from the repository root with the virtual environment active:

```sh
python -m ruff check --config backend/pyproject.toml backend scripts
python -m unittest discover -s backend/tests/contract -v
python -m unittest discover -s scripts/tests -v
python scripts/check_code_history.py
```

Then, from `apps/web`:

```sh
npm ci
npm test
npm run lint
npm run build
```

Finally, from the repository root with both ports free:

```sh
python scripts/check_wp1_integration.py --start-services
```

The last command starts the built web/backend processes, waits for readiness,
checks real HTTP, and stops only its own processes. It refuses occupied ports.
Omit `--start-services` to check an already-running local stack without stopping it.
It does not test browser microphone/audio playback or Cloudflare.

Ruff enforces Python correctness plus whitespace, indentation, spacing and
blank-line formatting. The rewriting `ruff format` command is not the gate because
it changes the required compact `#v...` markers. E262 is therefore excluded. Two
untouched worktree utilities have narrowly documented pre-existing W292 exceptions;
the rest of the Python tree is checked. No acceptance tests are excluded.

The history checker checks all source headers and new/modified code lines against
`HEAD` locally. To review a committed change, pass `--base <previous-commit>`.
CI uses the PR base or push's previous revision; a new branch's zero before-SHA
uses its merge base with `origin/main`. Existing untouched lines do not acquire
new tags retrospectively. JSON, lockfiles, Markdown, binary assets and the generated
Next.js declaration file are excluded. The tracked-path check is a filename/runtime
data safeguard, not a guarantee that arbitrary source text contains no secret.

## Exact owner gate (WP1.4 is level G)

Do not mark WP1 complete until hosted CI and this full procedure pass. On one
laptop and one phone, record model/OS/browser, date, deployed revision and observations:

1. Open `https://talkie.lookieman.dev/sim` and authenticate through human Access.
2. Confirm idle. Allow microphone access when prompted.
3. Hold the talk button. Hear the local chime and see listening.
4. Speak for roughly three seconds, then release. See thinking, then speaking;
   hear: “This is a KaKi-Talkie test reply. Your audio has not been interpreted.”
5. Confirm concise display text, followed by printing and idle. Confirm the 58 mm
   receipt shows its heading/body, `Source: canned test fixture`, and
   `Source checked: 05-Sep-2026 (fixture date)`, plus the no-retrieval wording.
6. Hold for more than 15 seconds. Recording must stop automatically and complete
   the same canned turn; release must not create another turn.
7. Exercise the zero-byte failure using the console helper below in the authenticated
   simulator tab. On a phone, use that browser's remote developer console. Confirm
   state `failed`, calm text, no slip, and audible playback of the failure line.
   Silence inside a non-empty recording still gets the canned answer in WP1;
   acoustic silence/usefulness detection is explicitly deferred to WP2.
8. Open a private/signed-out window. Confirm Access blocks `/sim` and API requests.
   Complete the unauthenticated POST/origin-observation checks in the Cloudflare
   instructions; an application 422 response is not an edge denial.
9. Verify the Mac listeners remain loopback-only. Confirm the schema and earlier
   regression gates still pass, and record the hosted CI result.

Zero-byte test helper (no credentials are embedded; same-origin session is used):

```javascript
const form = new FormData();
form.set("device_id", "web-simulator");
form.set("session_id", "wp1-owner-empty");
form.set("turn_id", crypto.randomUUID());
form.set("audio", new Blob([], { type: "audio/wav" }), "empty.wav");
const response = await fetch("/api/device/turn", { method: "POST", body: form });
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const result = await response.json();
console.assert(result.state === "failed" && result.slip_text === "");
console.assert(result.reply_text === "No audio was received. Please try recording again.");
await new Audio(result.reply_audio).play();
```

This helper tests the API response and browser playback directly; it does not
simulate an acoustic-silence detector or claim to exercise the simulator state
loop for the injected request. If autoplay is blocked, paste the following after
the helper and tap the visible temporary button. Reload the page to remove it:

```javascript
const play = document.createElement("button");
play.textContent = "Play zero-byte failure fixture";
play.onclick = () => new Audio(result.reply_audio).play();
document.body.append(play);
```

## Evidence mapping and completion boundary

| Gate | Automated evidence | Owner evidence still required |
| --- | --- | --- |
| WP1-AT-01–07 | Existing backend contracts, versioned health, HTTP integration | Observe deployed behavior |
| WP1-AT-08 | Simulator tests, ESLint, production build | Phone/laptop rendering |
| WP1-AT-09 | Existing recorder timer test | Real browser 15-second cap |
| WP1-AT-10 | Existing 40-word wrapping test; fixture receipt checks | Read rendered receipt |
| WP1-AT-11 | Explicit launcher and web-command assertions; HTTP integration | Mac listener inspection |
| WP1-AT-12 / X-AT-01 | Unchanged turn-schema snapshot test | None beyond reviewing results |
| X-AT-02 | Language-aware history checker and its tests; lint | Review changed-line markers |
| X-AT-03 | Tracked secret/runtime-path check | Review diff for actual credentials/data |
| X-AT-04 | Earlier suites run; schema retained | Review that assertions were preserved except authorised reconciliations |

Cloudflare protection, audible playback, laptop/phone operation, and Mac listener
inspection cannot be established by a green hosted unit-test job alone. WP2 real
STT/TTS/audio usefulness, WP3 retrieval, WP4 persistence/actions, and WP6 hardware
remain outside this unit.
