# v1.0 | 02-Sep-2026 | Define the required multipart device-turn input.

from dataclasses import dataclass
from typing import Annotated

from fastapi import File, Form, UploadFile


@dataclass
class TurnRequest:
    """Multipart input; identifiers are opaque, nonblank client-supplied strings."""

    audio: Annotated[UploadFile, File()]
    device_id: Annotated[str, Form(min_length=1, pattern=r"\S")]
    session_id: Annotated[str, Form(min_length=1, pattern=r"\S")]
    turn_id: Annotated[str, Form(min_length=1, pattern=r"\S")]
