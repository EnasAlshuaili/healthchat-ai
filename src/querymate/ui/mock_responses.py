"""Mock assistant replies for the UI-only preview.

No backend is connected. Every reply is static placeholder text that:
- never depends on the user's question (``mock_reply`` does not receive it),
- contains no medical information, and
- never uses dataset content (D-01).

When the UI is connected, replace ``mock_reply`` with the real pipeline
(safety router -> topic matching -> reviewed content), keeping the
``ReplyKind`` states so the interface can render each one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from querymate import config


class ReplyKind(StrEnum):
    PLACEHOLDER = "placeholder"
    FALLBACK = "fallback"
    EMERGENCY = "emergency"
    ERROR = "error"


@dataclass(frozen=True)
class MockReply:
    kind: ReplyKind
    title: str
    paragraphs: tuple[str, ...]
    is_mock: bool = True


# Generic wording only (D-07).
EMERGENCY_LINE = (
    "If you think you may be experiencing an emergency, contact local emergency "
    "services immediately."
)

_REPLIES = {
    ReplyKind.PLACEHOLDER: MockReply(
        kind=ReplyKind.PLACEHOLDER,
        title="Mock response: answers are not available yet",
        paragraphs=(
            "This is a placeholder. QueryMate's answer system is not connected to "
            "this preview, so your question has not been read, checked, or answered.",
            "For health concerns, please consult a qualified healthcare professional. "
            + EMERGENCY_LINE,
        ),
    ),
    ReplyKind.FALLBACK: MockReply(
        kind=ReplyKind.FALLBACK,
        title="Mock response: no relevant answer (preview)",
        paragraphs=(
            "This previews how QueryMate will respond when it cannot find reviewed "
            "information that fits a question.",
            "“I couldn’t find enough reliable information to answer this safely. "
            "Please rephrase your question or consult a qualified healthcare "
            "professional.”",
        ),
    ),
    ReplyKind.EMERGENCY: MockReply(
        kind=ReplyKind.EMERGENCY,
        title="Mock response: emergency notice (preview)",
        paragraphs=(
            "This previews the emergency notice style. It was **not** triggered by "
            "your message, which has not been analysed.",
            "Your message may describe an emergency. **Contact your local emergency "
            "services immediately** if you or someone else may be in danger.",
            "Do not wait for this chatbot to assess the situation.",
        ),
    ),
    ReplyKind.ERROR: MockReply(
        kind=ReplyKind.ERROR,
        title="Mock response: service unavailable (preview)",
        paragraphs=(
            "Sorry, the assistant is temporarily unavailable. Please try again later.",
            "If this is urgent, contact emergency services or a healthcare professional.",
        ),
    ),
}


def mock_reply(kind: ReplyKind | str = ReplyKind.PLACEHOLDER) -> MockReply:
    """Return the static mock reply for a UI state."""
    return _REPLIES[ReplyKind(kind)]


def validate_question(text: str | None) -> str | None:
    """Return an error message if the input cannot be sent, otherwise None.

    UI-side check only; the safety router performs its own validation (D-17).
    """
    if text is None or not text.strip():
        return "Please enter a question."
    if len(text) > config.MAX_INPUT_CHARS:
        return (
            "Your question is too long. Please shorten it to "
            f"{config.MAX_INPUT_CHARS:,} characters or fewer."
        )
    return None
