# WP1 browser simulator

The browser simulator uses the same multipart `POST /api/device/turn` contract
as the future physical client. Start the canned backend on `127.0.0.1:8000`,
then run the simulator locally from the repository root:

```text
cd apps/web
npm ci
npm run dev
```

Open `http://127.0.0.1:3000/sim`. Hold the talk button while speaking; release
to submit, or let the browser stop recording at the 15-second limit. The local
Next.js rewrite keeps the browser request same-origin and forwards only `/api/*`
to the existing backend. WP1.4 adds deployment/CI wiring without changing the
simulator interaction. Backend-provided prerecorded WAV data URIs use the existing
audio playback path; no browser service token or runtime TTS is needed.

Run the automated checks from `apps/web`:

```text
npm test
npm run lint
npm run build
```

After a production build, run `npm start` from `apps/web`. Both development and
production commands explicitly bind to `127.0.0.1:3000`.

The source/date printed in WP1 is a labelled test fixture, not retrieved evidence.
Zero-byte uploads return a spoken failure fixture. A non-empty silent recording
still receives the canned answer; real silence/usefulness detection belongs to WP2.

For actual HTTP integration, from the repository root with the backend virtual
environment active and ports 8000/3000 free:

```text
python scripts/check_wp1_integration.py --start-services
```

Follow the [Mac deployment and exact owner gate](../../infra/macos/README.md)
and [Cloudflare protection instructions](../../infra/cloudflare/README.md).
The phone/laptop manual gate remains required; unit tests do not prove audible
playback or edge authentication.
