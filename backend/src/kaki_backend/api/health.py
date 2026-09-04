# v1.0 | 02-Sep-2026 | Report availability of the canned backend.

from typing import Literal

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
def health() -> dict[str, Literal["ok"]]:
    return {"status": "ok"}
