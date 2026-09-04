# v1.0 | 02-Sep-2026 | Return deterministic canned turns without inference or state.

from kaki_backend.contracts.responses import TurnResponse, TurnState


def create_canned_turn(turn_id: str, has_audio: bool) -> TurnResponse:
    """Exercise the response contract without interpreting or retaining audio."""
    if has_audio:
        reply_text = "This is a KaKi-Talkie test reply. Your audio has not been interpreted."
        display_text = "KaKi-Talkie test reply."
        slip_text = "KAKI-TALKIE TEST\nThis is a sample English slip.\nNo advice was generated."
        state = TurnState.ANSWERED
    else:
        reply_text = "No audio was received. Please try recording again."
        display_text = "Please try recording again."
        slip_text = ""
        state = TurnState.FAILED

    return TurnResponse(
        turn_id=turn_id,
        reply_audio=None,
        reply_text=reply_text,
        display_text=display_text,
        slip_text=slip_text,
        language="en",
        state=state,
        case_id=None,
        sources=[],
    )
