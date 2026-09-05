# WP1 Cloudflare Tunnel and Access

This is a deployment recipe, not evidence that the account is configured or the
public gate has passed. Follow design.md section 15.2. Deploy only the canned WP1
backend and simulator. The owner must select the authorised human identities.

## Protect the hostname before publishing it

Create a self-hosted Access application for the entire `talkie.lookieman.dev`
hostname, with an explicit Allow policy for the team's human identities. Protect
the simulator, static assets, `/api/health`, and `/api/device/*` within that same
human session. Inspect existing, more-specific applications/policies for bypasses.
Do not add an Everyone/BYPASS policy or browser service tokens. Access checks are
performed at the edge; the local WP1 application does not implement authentication.

The simulator's existing `web-simulator` device ID identifies the client; it is
not an authentication secret. Same-origin browser requests carry the Access session.
Physical-device service authentication is deferred to WP6.

Cloudflare documents [whole-host protection and path precedence](https://developers.cloudflare.com/cloudflare-one/access-controls/policies/app-paths/)
and [self-hosted public applications](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/).

## Route to the two localhost origins

Use the existing account/tunnel if available. Keep the actual tunnel configuration
and credentials outside Git, for example in the service account's `.cloudflared`
directory. Never copy tokens, credentials JSON, or the account certificate into this
repository. DNS for the hostname must point to the intended tunnel.

For a locally managed tunnel, adapt this example outside Git. Replace the UUID and
credential path with the owner's values. Rules are ordered, with the most specific
paths first and a final unmatched-host rejection:

```yaml
tunnel: REPLACE_WITH_TUNNEL_UUID
credentials-file: /Users/websvc/.cloudflared/REPLACE_WITH_TUNNEL_UUID.json
ingress:
  - hostname: talkie.lookieman.dev
    path: ^/api/device/.*$
    service: http://127.0.0.1:8000
  - hostname: talkie.lookieman.dev
    path: ^/api/health$
    service: http://127.0.0.1:8000
  - hostname: talkie.lookieman.dev
    service: http://127.0.0.1:3000
  - service: http_status:404
```

For a remotely managed tunnel, configure the same ordered hostname/path/service
routes in the dashboard; do not assume a local YAML file controls that tunnel.
Do not open router ports or bind either application to the LAN. The existing
Next.js rewrite also supports local development; production device/health traffic
uses the direct tunnel routes above.

With the external local configuration at the default `.cloudflared/config.yml`:

```sh
cloudflared tunnel ingress validate
cloudflared tunnel ingress rule https://talkie.lookieman.dev/api/device/turn
cloudflared tunnel ingress rule https://talkie.lookieman.dev/api/device/pending
cloudflared tunnel ingress rule https://talkie.lookieman.dev/api/health
cloudflared tunnel ingress rule https://talkie.lookieman.dev/sim
cloudflared tunnel ingress rule https://unmatched.example/sim
```

Expected results are respectively backend, backend, backend, web, and the final 404
rule. Validation proves configuration syntax/matching, not live Access protection.
See Cloudflare's [configuration-file reference](https://developers.cloudflare.com/tunnel/advanced/local-management/configuration-file/).

## Owner security evidence

1. Start both localhost services using [the Mac instructions](../macos/README.md).
   Configure Access first, then start the tunnel and verify the intended DNS route.
2. In a signed-out/private browser, request `/sim`, `/api/health`, and
   `/api/device/pending`. Confirm an Access login/denial, not application HTML/JSON.
3. Send an unauthenticated POST without following redirects, for example:

   ```sh
   curl --max-time 10 -i -X POST 'https://talkie.lookieman.dev/api/device/turn?wp1_gate=unauth-check'
   ```

   A login redirect or edge denial is acceptable. An application's 422 validation
   response is NOT acceptable: it proves the request reached FastAPI.
4. Observe the running backend's access output while sending that uniquely labelled
   request. Confirm it never reaches FastAPI. Establish that the logs work with an
   authenticated `/api/health?wp1_gate=auth-control` request. Record status/redirect
   evidence and origin observation without copying cookies/tokens.
5. Authenticate in the normal browser. Confirm `/sim` and browser API calls work
   through the same human session, with no `CF-Access-Client-Secret` in JavaScript.
6. Complete the phone/laptop gate in the Mac instructions. Record date, device,
   browser, deployed revision, and pass/fail observations outside credential files.

The hosted CI job neither configures Cloudflare nor claims these checks passed.
Tailscale Serve remains optional and is not a WP1 gate.
