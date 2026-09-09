# WP1.4 localhost deployment and owner gate

This file records the WP1.4 owner gate (level G) and remains the reference
for rerunning it when a change touches the WP1 contract, browser or
deployment boundary. Installation is governed by [`setup.md`](setup.md);
service start order, validation and evidence for later work packages are
governed by the
[WP validation runbook](../../docs/04-prototype/wp-validation-runbook.md).

The design baseline is the Mac Mini, with FastAPI on `127.0.0.1:8000` and the
web application on `127.0.0.1:3000`. This unit adds no model services,
database, launchd installation, or hardware integration. Keep runtime data
outside Git under `KAKI_DATA_ROOT` (baseline `/Users/websvc/kaki-talkie-data`).

## Start the WP1 stack for the gate

Install per `setup.md` sections 7.1 (backend `.venv`) and 14 (simulator).
Start two foreground processes in separate terminals.

From the repository root with `.venv` active:

```sh
python -m kaki_backend.main
```

From `apps/web` after `npm run build`:

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
Both health requests must return `status: ok` with the application version.
Open `http://127.0.0.1:3000/sim` for local testing. Phone testing uses the
protected HTTPS hostname, not a LAN bind. Follow
[Cloudflare setup and verification](../cloudflare/README.md). Stop only these
foreground services with Ctrl+C when finished.

## Tier A regression

The WP1 Tier A commands (Ruff, contract and script tests, web lint/test/
build, and `scripts/check_wp1_integration.py`) are maintained in runbook
sections 6 and 7.2.2 Test 5 and in the CI configuration. Do not maintain a
third copy here.

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
| X-AT-02 | No history metadata gate; Ruff retained | History convention is advisory |
| X-AT-03 | No tracked-path checker | Review diff for actual credentials/data |
| X-AT-04 | Earlier suites run; schema retained | Review that assertions were preserved except authorised reconciliations |

Cloudflare protection, audible playback, laptop/phone operation, and Mac listener
inspection cannot be established by a green hosted unit-test job alone. WP2 real
STT/TTS/audio usefulness, WP3 retrieval, WP4 persistence/actions, and WP6 hardware
remain outside this unit.
