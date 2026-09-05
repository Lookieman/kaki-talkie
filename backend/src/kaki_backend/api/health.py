# v1.1 | 05-Sep-2026 | Include the application version in health responses.
# v1.0 | 02-Sep-2026 | Report availability of the canned backend.

from fastapi import APIRouter, Request  #v1.1

router = APIRouter()


@router.get("/api/health")
def health(request: Request) -> dict[str, str]:  #v1.1
    return {"status": "ok", "version": request.app.version}  #v1.1
