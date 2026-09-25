# v1.1 | 24-Sep-2026 | Pitch receipt page: GET the most recent booking.
# v1.0 | 18-Sep-2026 | WP6.6 admin surface: per-device language, one canned push, state.
"""Serve the demo admin surface (design.md 5.5): four routes, state only.

The admin surface lets a second operator steer the demo from a phone: switch
one device's reply language, and release one canned push. It writes state and
reads state, and does nothing else — no route here enters the turn pipeline,
calls a model or synthesises audio. The push audio is a pre-synthesised
fixture the store hands over as a data URL.

Authentication is the application's own bearer token (`KAKI_ADMIN_TOKEN`),
checked before any state change and failing closed when unset (WP6-AT-17).
Cloudflare Access guards the tunnel path on top of this; the token is what
guards the loopback path, which exists for the times the tunnel is down. The
WP6.4 device service credential is a different secret and is never accepted
here.

`GET /api/admin/booking/latest` feeds the standalone `/receipt` page shown on
the projector: the newest booking from whichever client made it. It reads
state only and sits behind the same admin token.

Every write names its `device_id` explicitly. No route infers a target from
recent activity (owner decision, 18-Sep-2026; design.md 5.5).
"""

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from kaki_backend.config import AdminSettings
from kaki_backend.persistence.admin_store import (
    REPLY_LANGUAGES,
    AdminStore,
    UnknownMessage,
)

router = APIRouter()

BEARER_PREFIX = "bearer "


def get_admin_store(request: Request) -> AdminStore:
    """Return the application-owned admin store."""
    return request.app.state.admin_store


def get_admin_settings(request: Request) -> AdminSettings:
    """Return the admin settings the application was started with."""
    return request.app.state.admin_settings


def require_admin_token(request: Request) -> None:
    """Reject the request before any state change unless the bearer token matches.

    Fails closed: no configured token means 403 for everyone, with a message
    that says what to configure. Comparison is constant-time; the failure
    responses are deliberately identical for a missing and a wrong token, so
    the route confirms nothing about the secret.
    """
    settings: AdminSettings = request.app.state.admin_settings
    if not settings.enabled:
        raise HTTPException(
            status_code=403,
            detail="The admin surface is disabled: set KAKI_ADMIN_TOKEN and restart.",
        )
    header = request.headers.get("authorization", "")
    supplied = header[len(BEARER_PREFIX):] if header.lower().startswith(BEARER_PREFIX) else ""
    if not supplied or not hmac.compare_digest(supplied, settings.token):
        raise HTTPException(status_code=401, detail="Admin bearer token required.")


class ConfigRequest(BaseModel):
    """One device's reply-language override."""

    model_config = ConfigDict(strict=True)
    device_id: str = Field(min_length=1, max_length=128)
    reply_language: str


class PushRequest(BaseModel):
    """Release one seeded canned message for one device."""

    model_config = ConfigDict(strict=True)
    device_id: str = Field(min_length=1, max_length=128)
    message_key: str = Field(default="cdc-vouchers-available", min_length=1, max_length=128)


@router.post("/api/admin/config", dependencies=[Depends(require_admin_token)])
def set_config(
    body: ConfigRequest, store: Annotated[AdminStore, Depends(get_admin_store)],
) -> dict[str, object]:
    """Set one device's reply language; `auto` returns the decision to the policy."""
    try:
        store.set_reply_language(body.device_id, body.reply_language)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return {"device_id": body.device_id.strip(), "reply_language": body.reply_language}


@router.post("/api/admin/push", dependencies=[Depends(require_admin_token)])
def push_message(
    body: PushRequest, store: Annotated[AdminStore, Depends(get_admin_store)],
) -> dict[str, object]:
    """Mark the seeded message queued for one named device.

    A repeated push re-arms a delivered message; that is the documented reset
    between rehearsals. The response reports the queue state so the admin
    page's status line can confirm the push armed.
    """
    try:
        state = store.push(body.message_key, body.device_id)
    except UnknownMessage as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return {
        "message_key": state.message_key, "state": state.state,
        "target_device_id": state.target_device_id, "pushed_at": state.pushed_at,
        "delivered_count": state.delivered_count,
    }


@router.get("/api/admin/state", dependencies=[Depends(require_admin_token)])
def admin_state(
    store: Annotated[AdminStore, Depends(get_admin_store)],
    settings: Annotated[AdminSettings, Depends(get_admin_settings)],
) -> dict[str, object]:
    """Return what is live: per-device config, the queue, and the page's default target."""
    return {
        "default_device": settings.default_device,
        "reply_languages": list(REPLY_LANGUAGES),
        "config": store.config_rows(),
        "messages": [
            {
                "message_key": message.message_key, "state": message.state,
                "target_device_id": message.target_device_id,
                "pushed_at": message.pushed_at, "delivered_at": message.delivered_at,
                "delivered_count": message.delivered_count,
            }
            for message in store.message_states()
        ],
    }


@router.get("/api/admin/booking/latest", dependencies=[Depends(require_admin_token)])  #v1.1
def latest_booking(
    store: Annotated[AdminStore, Depends(get_admin_store)],
) -> dict[str, object]:
    """Return the most recent booking as `{"booking": {...}}`, or `{"booking": null}`.

    The booking carries `case_id`, `completed_at` (UTC ISO 8601), `slip_text`
    and `device_id`. Before any booking the value is null, which the receipt
    page shows as its waiting state.
    """
    booking = store.latest_booking()
    if booking is None:
        return {"booking": None}
    return {"booking": {
        "case_id": booking.case_id, "completed_at": booking.completed_at,
        "slip_text": booking.slip_text, "device_id": booking.device_id,
    }}
