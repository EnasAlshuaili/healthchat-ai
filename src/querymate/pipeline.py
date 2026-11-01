"""Response pipeline: router first, then curated knowledge (docs/API_CONTRACT.md).

`respond(question)` runs the Safety & Scope Router first and returns one fixed
reply. Execution order:

1. `safety.route(question)` receives the question unchanged. The router does all
   input validation (empty, non-text, over-length) and keeps its rules, reason
   codes, and priorities (D-17, v0.1.1).
2. The decision is checked: a real `RouteDecision`, a known route, known reason
   codes, and the router build that D-20 approved.
3. Every route except `PROCEED` selects a fixed template. `INVALID_INPUT` is
   resolved by reason code.
4. `PROCEED` only: `knowledge.retrieve` looks up an owner-reviewed curated entry.
   No match returns the safe fallback (D-02).

The topic matcher and the TF-IDF retrieval baseline are never called, nothing is
read from the dataset (D-01), and nothing is stored or logged except the reason a
reply failed closed. Replies never contain the question. Any failure returns the
approved safe fallback with `versions.router = None` (fail closed, R-10).

The router is a keyword prototype. These replies are not clinical triage. Curated
answers are owner-reviewed educational content: they have not been clinically
reviewed or clinically validated.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from querymate import knowledge, safety
from querymate.ui.content import DISCLAIMER

logger = logging.getLogger("querymate.pipeline")

API_VERSION = "0.3"
TEMPLATE_VERSION = "templates-0.1"

# The router build the templates and route mapping were approved for (D-20).
# The over-length reply says "1,000 characters", so the limits are part of it.
APPROVED_ROUTER_VERSION = "0.1.1"
APPROVED_MAX_INPUT_CHARS = 1_000
APPROVED_SCAN_LIMIT_CHARS = 20_000

Kind = Literal[
    "curated_answer",
    "mock_answer",
    "safe_fallback",
    "emergency",
    "crisis",
    "decline_diagnosis",
    "decline_dosage",
    "out_of_scope",
    "invalid_input",
]
ContentSource = Literal["curated_owner_reviewed", "mock_placeholder", "safety_template", "input_check"]


@dataclass(frozen=True)
class Template:
    kind: Kind
    title: str
    paragraphs: tuple[str, ...]


# --- Approved templates (docs/API_CONTRACT.md "Reply templates", templates-0.1) ---
# Exact text; tests compare every template with the contract.

EMERGENCY_LINE = (
    "If you think you may be experiencing an emergency, contact local emergency services immediately."
)

_EMERGENCY_PARAGRAPHS = (
    "If you or someone else may be in immediate danger, contact local emergency services immediately.",
    "HealthChat AI is an educational prototype and cannot provide crisis intervention or assess immediate "
    "safety. Do not wait for a response from HealthChat AI if urgent help may be needed.",
)

_CRISIS_SUPPORT = (
    "If you are thinking about harming yourself, please reach out to someone you trust who can support "
    "you now. If you or someone else may have taken too much of a medicine or other substance, seek "
    "emergency help immediately. If possible, stay with someone you trust while getting help."
)

TEMPLATES: dict[str, Template] = {
    "emergency": Template("emergency", "Possible emergency", _EMERGENCY_PARAGRAPHS),
    # Approved structure: the emergency paragraphs first and unchanged, then crisis support.
    "crisis": Template("crisis", "Please get help now", _EMERGENCY_PARAGRAPHS + (_CRISIS_SUPPORT,)),
    "decline_diagnosis": Template(
        "decline_diagnosis",
        "HealthChat AI can't diagnose",
        (
            "HealthChat AI is an educational prototype and cannot diagnose conditions or say what may be "
            "causing symptoms.",
            "Please talk to a doctor or another qualified healthcare professional, who can assess your "
            "situation. If symptoms are severe, getting worse, or worrying you, seek professional care.",
            EMERGENCY_LINE,
        ),
    ),
    "decline_dosage": Template(
        "decline_dosage",
        "HealthChat AI can't advise on medicines or doses",
        (
            "HealthChat AI is an educational prototype and cannot recommend medicines, suggest doses, or "
            "advise on starting, stopping, changing, or combining medicines.",
            "For questions about medicines, please ask a pharmacist, your prescriber, or another qualified "
            "healthcare professional, or check the official information leaflet that comes with the medicine.",
            EMERGENCY_LINE,
        ),
    ),
    "out_of_scope": Template(
        "out_of_scope",
        "This question is outside what HealthChat AI covers",
        (
            "HealthChat AI only provides general educational information about human health topics, so it "
            "can't help with this question.",
            "Please try a general health question, or ask a suitable professional or service about this topic.",
            EMERGENCY_LINE,
        ),
    ),
    "safe_fallback": Template(
        "safe_fallback",
        "HealthChat AI can't answer this safely",
        (
            # 06_UI_UX_Design §4 low-confidence wording.
            "I couldn't find enough reliable information to answer this safely. Please rephrase your "
            "question or consult a qualified healthcare professional.",
            EMERGENCY_LINE,
        ),
    ),
    "invalid_input:empty": Template(
        "invalid_input",
        "Please enter a question.",
        ("Type a general health question, then send it.",),
    ),
    "invalid_input:too_long": Template(
        "invalid_input",
        "Your question is too long.",
        ("Please shorten it to 1,000 characters or fewer.", EMERGENCY_LINE),
    ),
    "mock_answer": Template(
        "mock_answer",
        "Mock response: answers are not available yet",
        (
            "This is a placeholder. HealthChat AI's answer system is not connected, so your question has not "
            "been checked or answered.",
            "For health concerns, please consult a qualified healthcare professional. " + EMERGENCY_LINE,
        ),
    ),
}

# Route -> template key. INVALID_INPUT is resolved by reason code (see _template_key),
# and PROCEED by the knowledge lookup (see _answer). `mock_answer` is no longer selected.
_ROUTE_TEMPLATES: dict[safety.Route, str] = {
    safety.Route.CRISIS: "crisis",
    safety.Route.EMERGENCY: "emergency",
    safety.Route.DOSAGE: "decline_dosage",
    safety.Route.DIAGNOSIS: "decline_diagnosis",
    safety.Route.SAFE_FALLBACK: "safe_fallback",
    safety.Route.OUT_OF_SCOPE: "out_of_scope",
}


@dataclass(frozen=True)
class ChatResult:
    """One reply in the shape of API Contract v0.3, without the per-request `request_id`.

    `is_mock`, `content_source`, and the abstention fields are derived from `kind`,
    so the contract invariants cannot be broken by construction.
    """

    kind: Kind
    title: str
    paragraphs: tuple[str, ...]
    router_version: str | None  # "0.1.1" only when the reply is based on a router decision
    sources: tuple[knowledge.Source, ...] = ()  # curated answers only
    review_status: str | None = None            # curated answers only
    knowledge_version: str | None = None        # curated answers only

    @property
    def is_mock(self) -> bool:
        return self.kind == "mock_answer"

    @property
    def content_source(self) -> ContentSource:
        if self.kind == "curated_answer":
            return "curated_owner_reviewed"
        if self.kind == "mock_answer":
            return "mock_placeholder"
        if self.kind == "invalid_input":
            return "input_check"
        return "safety_template"

    def to_dict(self, request_id: str) -> dict:
        """The full v0.3 `/api/chat` response body for this reply."""
        return {
            "api_version": API_VERSION,
            "request_id": request_id,
            "kind": self.kind,
            "content_source": self.content_source,
            "message": {"title": self.title, "paragraphs": list(self.paragraphs)},
            "sources": [
                {"title": s.title, "organization": s.organization, "url": s.url} for s in self.sources
            ],
            "review_status": self.review_status,
            "is_mock": self.is_mock,
            "abstained": False,  # the matcher is not connected
            "abstain_reason": None,
            "disclaimer": DISCLAIMER,
            "versions": {
                "router": self.router_version,
                "matcher": None,
                "content": TEMPLATE_VERSION,
                "knowledge": self.knowledge_version,
            },
        }


class UnsupportedDecision(Exception):
    """A router result the pipeline cannot map safely. Always fails closed."""


def _result(key: str, router_version: str | None) -> ChatResult:
    template = TEMPLATES[key]
    return ChatResult(template.kind, template.title, template.paragraphs, router_version)


def _fail_closed(reason: str, exc: BaseException | None = None) -> ChatResult:
    # Log a fixed reason and the exception type only: messages and tracebacks may contain user text.
    detail = f" ({type(exc).__name__})" if exc is not None else ""
    logger.error("Pipeline failed closed: %s%s", reason, detail)
    return _result("safe_fallback", router_version=None)


def _check_decision(decision: object) -> safety.RouteDecision:
    if not isinstance(decision, safety.RouteDecision):
        raise UnsupportedDecision("not a RouteDecision")
    if not isinstance(decision.route, safety.Route):
        raise UnsupportedDecision("undefined route")
    codes = decision.reason_codes
    if not isinstance(codes, tuple) or not codes or not all(isinstance(c, str) for c in codes):
        raise UnsupportedDecision("malformed reason codes")
    if not set(codes) <= safety.REASON_CODES:
        raise UnsupportedDecision("unknown reason code")
    if (
        decision.router_version != APPROVED_ROUTER_VERSION
        or safety.ROUTER_VERSION != APPROVED_ROUTER_VERSION
        or safety.MAX_INPUT_CHARS != APPROVED_MAX_INPUT_CHARS
        or safety.SCAN_LIMIT_CHARS != APPROVED_SCAN_LIMIT_CHARS
    ):
        raise UnsupportedDecision("router build not approved by D-20")
    return decision


def _template_key(decision: safety.RouteDecision) -> str:
    if decision.route is safety.Route.INVALID_INPUT:
        # Contract v0.2 reason-code selection; anything else fails closed.
        if "input:too_long" in decision.reason_codes:
            return "invalid_input:too_long"
        if {"input:empty", "input:not_text"} & set(decision.reason_codes):
            return "invalid_input:empty"
        raise UnsupportedDecision("INVALID_INPUT without an input reason code")
    if decision.route not in _ROUTE_TEMPLATES:
        raise UnsupportedDecision("route has no approved template")
    return _ROUTE_TEMPLATES[decision.route]


def connected_knowledge_version() -> str | None:
    """The curated knowledge version in use, or None if it could not be loaded."""
    return knowledge.KNOWLEDGE_VERSION if knowledge.is_available() else None


def _answer(question: str, router_version: str) -> ChatResult:
    """After PROCEED only: the curated entry approved for this question, or the safe fallback."""
    entry = knowledge.retrieve(question)
    if entry is None:
        return _result("safe_fallback", router_version)
    if entry.review_status != knowledge.DISPLAYABLE_REVIEW_STATUS or not entry.sources:
        raise UnsupportedDecision("curated entry may not be displayed")
    return ChatResult(
        "curated_answer", entry.title, entry.paragraphs, router_version,
        sources=entry.sources, review_status=entry.review_status,
        knowledge_version=knowledge.KNOWLEDGE_VERSION,
    )


def respond(question: object) -> ChatResult:
    """Return the approved reply for one question. Stateless; never raises."""
    try:
        decision = safety.route(question)
    except Exception as exc:  # noqa: BLE001 - fail closed (R-10)
        return _fail_closed("router raised", exc)
    try:
        decision = _check_decision(decision)
        if "router:error" in decision.reason_codes:
            # The router's own fail-safe: no routing rules were applied.
            return _fail_closed("router internal error")
        if decision.route is safety.Route.PROCEED:
            return _answer(question, decision.router_version)
        return _result(_template_key(decision), router_version=decision.router_version)
    except Exception as exc:  # noqa: BLE001 - fail closed (R-10)
        return _fail_closed("unsupported router decision or pipeline error", exc)
