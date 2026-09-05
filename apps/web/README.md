# WP1.3 browser simulator

The browser simulator uses the same multipart `POST /api/device/turn` contract
as the future physical client. Start the canned backend on `127.0.0.1:8000`,
then run the simulator locally from the repository root:

```text
cd apps/web
npm install
npm run dev
```

Open `http://127.0.0.1:3000/sim`. Hold the talk button while speaking; release
to submit, or let the browser stop recording at the 15-second limit. The local
Next.js rewrite keeps the browser request same-origin and forwards only `/api/*`
to the existing backend. Cloudflare, CI and deployment wiring remain WP1.4.

Run the automated checks from `apps/web`:

```text
npm test
npm run lint
npm run build
```
