"""Request, response, and error models for docs/API_CONTRACT.md v0.3 (curated_single_topic mode)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, model_validator

API_VERSION = "0.3"

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
# "reviewed_content" is reserved by the contract and deliberately not accepted yet.
ContentSource = Literal["curated_owner_reviewed", "mock_placeholder", "safety_template", "input_check"]
ReviewStatus = Literal["owner_reviewed"]  # owner review of educational content; never clinical review
AbstainReason = Literal["no_overlap", "below_min_score", "below_min_margin", "matcher_unavailable"]
ErrorCode = Literal[
    "not_found",
    "method_not_allowed",
    "payload_too_large",
    "unsupported_media_type",
    "invalid_request",
    "internal_error",
]

# API_CONTRACT v0.3 "kind values": content_source is determined by kind.
CONTENT_SOURCE_BY_KIND: dict[str, str] = {
    "curated_answer": "curated_owner_reviewed",
    "mock_answer": "mock_placeholder",
    "invalid_input": "input_check",
    "emergency": "safety_template",
    "crisis": "safety_template",
    "decline_diagnosis": "safety_template",
    "decline_dosage": "safety_template",
    "out_of_scope": "safety_template",
    "safe_fallback": "safety_template",
}

_STRICT = ConfigDict(extra="forbid", strict=True)


class ChatRequest(BaseModel):
    """A JSON object with exactly one string field. No length limit here: see the contract."""

    model_config = _STRICT

    question: StrictStr


class Message(BaseModel):
    model_config = _STRICT

    title: StrictStr
    paragraphs: list[StrictStr] = Field(min_length=1, max_length=5)


class Source(BaseModel):
    model_config = _STRICT

    title: StrictStr = Field(min_length=1)
    organization: StrictStr = Field(min_length=1)
    url: StrictStr = Field(pattern=r"^https://\S+$")


class ChatVersions(BaseModel):
    model_config = _STRICT

    router: StrictStr | None  # "0.1.1" only when the reply is based on a router decision
    matcher: None  # the matcher is not connected
    content: Literal["templates-0.1"]
    knowledge: StrictStr | None  # set only on curated answers


class ChatResponse(BaseModel):
    model_config = _STRICT

    api_version: Literal["0.3"]
    request_id: StrictStr
    kind: Kind
    content_source: ContentSource
    message: Message
    sources: list[Source]
    review_status: ReviewStatus | None
    is_mock: StrictBool
    abstained: StrictBool
    abstain_reason: AbstainReason | None
    disclaimer: StrictStr
    versions: ChatVersions

    @model_validator(mode="after")
    def _contract_invariants(self) -> "ChatResponse":
        if self.is_mock != (self.kind == "mock_answer"):
            raise ValueError("is_mock must be true if and only if kind is mock_answer")
        if self.content_source != CONTENT_SOURCE_BY_KIND[self.kind]:
            raise ValueError("content_source does not match kind")
        if self.abstained or self.abstain_reason is not None:
            raise ValueError("the matcher is not connected: no abstention")
        curated = self.kind == "curated_answer"
        if curated != bool(self.sources):
            raise ValueError("sources must be present if and only if kind is curated_answer")
        if curated != (self.review_status is not None):
            raise ValueError("review_status must be set if and only if kind is curated_answer")
        if curated != (self.versions.knowledge is not None):
            raise ValueError("versions.knowledge must be set if and only if kind is curated_answer")
        if curated and self.versions.router is None:
            raise ValueError("a curated answer must be based on a router decision")
        return self


class HealthVersions(BaseModel):
    model_config = _STRICT

    router: StrictStr  # the connected router version (not per-request execution)
    matcher: None
    content: Literal["templates-0.1"]
    knowledge: StrictStr | None  # None if the curated knowledge could not be loaded


class HealthResponse(BaseModel):
    model_config = _STRICT

    status: Literal["ok"] = "ok"
    api_version: Literal["0.3"] = API_VERSION
    mode: Literal["curated_single_topic"] = "curated_single_topic"
    versions: HealthVersions


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
