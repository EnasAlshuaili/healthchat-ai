"""Fixed reply templates for phase A (mock-only).

`check_question` is the only code that looks at the question, and it returns an
input-check result, never text. The reply functions take no question, so reply
content cannot depend on what was asked. Templates contain no medical
information and no dataset text (D-01), and use generic emergency wording (D-07).
"""

from __future__ import annotations

import re
from typing import Literal

from querymate import config
from querymate.api.schemas import Kind, Message

InputCheck = Literal["ok", "empty", "too_long"]

# Same normalisation as querymate.cleaning.normalize_whitespace, which the router
# uses for its length check (D-17); copied so the API does not import dataset code.
_WHITESPACE_RUN = re.compile(r"\s+")

EMERGENCY_LINE = (
    "If you think you may be experiencing an emergency, contact local emergency "
    "services immediately."
)

_MOCK_ANSWER = Message(
    title="Mock response: answers are not available yet",
    paragraphs=[
        "This is a placeholder. QueryMate's answer system is not connected, so your "
        "question has not been checked or answered.",
        "For health concerns, please consult a qualified healthcare professional. "
        + EMERGENCY_LINE,
    ],
)

_EMPTY = Message(
    title="Please enter a question.",
    paragraphs=["Type a general health question, then send it."],
)

_TOO_LONG = Message(
    title="Your question is too long.",
    paragraphs=[
        f"Please shorten it to {config.MAX_INPUT_CHARS:,} characters or fewer.",
        EMERGENCY_LINE,
    ],
)


def check_question(question: str) -> InputCheck:
    """Phase A input checks only (API_CONTRACT validation rows 4-5). No content analysis."""
    normalized = _WHITESPACE_RUN.sub(" ", question).strip()
    if not normalized:
        return "empty"
    if len(normalized) > config.MAX_INPUT_CHARS:
        return "too_long"
    return "ok"


def mock_answer() -> tuple[Kind, Message]:
    """The fixed mock answer. Deliberately takes no arguments."""
    return "mock_answer", _MOCK_ANSWER


def reply_for(check: InputCheck) -> tuple[Kind, Message]:
    if check == "empty":
        return "invalid_input", _EMPTY
    if check == "too_long":
        return "invalid_input", _TOO_LONG
    return mock_answer()
