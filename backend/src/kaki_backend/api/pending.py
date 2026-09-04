# v1.0 | 04-Sep-2026 | Expose the empty WP1 pending-item placeholder.

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/device/pending", response_model=list[dict[str, object]])
def pending_items() -> list[dict[str, object]]:
    """Return no due items until the case lifecycle is implemented in WP4."""
    return []
