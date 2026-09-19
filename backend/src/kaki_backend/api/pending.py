# v1.1 | 18-Sep-2026 | WP6.6: deliver queued admin pushes to the named device, once.
# v1.0 | 04-Sep-2026 | Expose the empty WP1 pending-item placeholder.

"""Serve due nudges to the polling client, delivering each exactly once.

The path and the empty default are unchanged since WP1: a call with no
`device_id`, or for a device with nothing queued, returns `[]` (WP1-AT-05).
The WP6.1 device client, which sends no `device_id`, therefore keeps seeing
the empty list it has always seen; the Pi's pending behaviour arrives with
WP6.5.

With a `device_id`, the admin store's atomic fetch-and-mark hands over every
message queued for that device and marks it delivered in the same
transaction, so a 3-second poll cannot replay a push (design.md 5.4,
WP6-AT-16). Delivery is scoped to the named device: the simulator and the Pi
must carry different identities, or one will consume the other's nudge
(runbook 11.1 WP6.6).
"""

from fastapi import APIRouter, Query, Request

router = APIRouter()


@router.get("/api/device/pending", response_model=list[dict[str, object]])
def pending_items(
    request: Request, device_id: str | None = Query(default=None, max_length=128),
) -> list[dict[str, object]]:
    """Return this device's due messages, marking them delivered as they leave."""
    if not device_id or not device_id.strip():
        return []
    return [
        {
            "id": message.message_id,
            "kind": "nudge",
            "text": message.text,
            "language": message.language,
            "audio": message.audio,
            "pushed_at": message.pushed_at,
        }
        for message in request.app.state.admin_store.take_due(device_id.strip())
    ]
