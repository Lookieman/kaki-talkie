# v1.0 | 20-Sep-2026 | WP6.4 device service authentication for every /api/device/* route.
"""Require the device service bearer token before any device route runs.

`require_device_token` is attached to each `/api/device/*` route as a
dependency, so FastAPI rejects an unauthenticated request before the request
body is read and before any handler or the turn service runs: rejection
happens before any state change (WP6-AT-05). `/api/health` stays open, since
readiness must be checkable before a credential is configured.

The credential is `KAKI_DEVICE_TOKEN`, a machine secret the Pi reads from
`/etc/kaki/device.toml`. It is deliberately a different secret from
`KAKI_ADMIN_TOKEN` and is never accepted on `/api/admin/*`; likewise the
admin token buys nothing here. The check mirrors the admin one: fail closed
when unset, constant-time comparison, and identical responses for a missing
and a wrong token so the route confirms nothing about the secret.
"""

import hmac

from fastapi import HTTPException, Request

from kaki_backend.config import DeviceAuthSettings

BEARER_PREFIX = "bearer "


def get_device_settings(request: Request) -> DeviceAuthSettings:
    """Return the device auth settings the application was started with."""
    return request.app.state.device_settings


def require_device_token(request: Request) -> None:
    """Reject the request before any state change unless the bearer token matches.

    Fails closed: no configured token means 403 for everyone, with a message
    that says what to configure. Comparison is constant-time; the failure
    responses are deliberately identical for a missing and a wrong token.
    """
    settings: DeviceAuthSettings = request.app.state.device_settings
    if not settings.enabled:
        raise HTTPException(
            status_code=403,
            detail="The device path is disabled: set KAKI_DEVICE_TOKEN and restart.",
        )
    header = request.headers.get("authorization", "")
    supplied = header[len(BEARER_PREFIX):] if header.lower().startswith(BEARER_PREFIX) else ""
    if not supplied or not hmac.compare_digest(supplied, settings.token):
        raise HTTPException(status_code=401, detail="Device bearer token required.")
