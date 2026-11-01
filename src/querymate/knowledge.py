"""Curated knowledge entries and deterministic retrieval (Phase D, curated/topic_content.json).

`curated/topic_content.json` holds owner-reviewed educational content, written from
named public sources. It contains no dataset text, and this module never reads the
dataset (D-01). The review recorded there is the project owner's review of educational
content only: it is not clinical review or medical validation (D-11).

Retrieval is an exact lookup: a question matches only if, after normalising case,
punctuation, and spacing, it equals an approved question. There is no scoring,
threshold, or keyword matching, because the router returns PROCEED for wordings the
general answer must not cover (babies, pregnancy, symptoms, added questions, ...).
No match means None, and the caller shows the safe fallback (D-02).

Only `owner_reviewed` entries can be retrieved. The file is read once at import, so
answering a question opens no files. If it is missing or invalid, `retrieve` raises
KnowledgeUnavailable and the pipeline fails closed.

Callers must run the Safety & Scope Router first: this module makes no safety or
scope decision (D-15(d), D-17).
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from querymate import config

logger = logging.getLogger("querymate.knowledge")

CONTENT_FILE = config.PROJECT_ROOT / "curated" / "topic_content.json"
KNOWLEDGE_VERSION = "0.1.0"

DISPLAYABLE_REVIEW_STATUS = "owner_reviewed"
REVIEW_STATUSES = {"pending_owner_review", DISPLAYABLE_REVIEW_STATUS}
CLINICAL_REVIEW = "not_clinically_reviewed"  # the only accepted value (D-11)
MAX_PARAGRAPHS = 5  # API contract limit for message.paragraphs

_ENTRY_ID = re.compile(r"KN-\d{4}")
_TOPIC_ID = re.compile(r"TOP-\d{3}")
_NON_WORD = re.compile(r"[\W_]+")

_TOP_KEYS = {"knowledge_version", "entries"}
_ENTRY_KEYS = {"entry_id", "topic_id", "title", "paragraphs", "approved_questions", "review", "sources",
               "statements"}
_REVIEW_KEYS = {"review_status", "clinical_review", "reviewer", "reviewed_on", "note"}
_SOURCE_KEYS = {"source_id", "title", "organization", "url", "page_date", "last_reviewed", "next_review_due",
                "checked_on", "review_overdue_when_checked", "how_checked"}
_STATEMENT_KEYS = {"text", "evidence"}
_EVIDENCE_KEYS = {"source_id", "section", "quote"}


class KnowledgeError(ValueError):
    """The content file breaks the rules in `validate`."""


class KnowledgeUnavailable(RuntimeError):
    """The content could not be loaded. Callers must fail closed."""


@dataclass(frozen=True)
class Source:
    title: str
    organization: str
    url: str


@dataclass(frozen=True)
class Entry:
    entry_id: str
    topic_id: str
    title: str
    paragraphs: tuple[str, ...]
    sources: tuple[Source, ...]
    review_status: str
    question_keys: frozenset[str]


def normalize_question(question: str) -> str:
    """Lowercase; turn punctuation and spacing into single spaces. Words are never removed."""
    return _NON_WORD.sub(" ", unicodedata.normalize("NFKC", question).casefold()).strip()


def _require(condition: bool, problem: str) -> None:
    if not condition:
        raise KnowledgeError(problem)


def _is_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_date(value: object) -> bool:
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _check_keys(value: object, keys: set[str], name: str) -> None:
    _require(isinstance(value, dict) and set(value) == keys, f"{name}: wrong fields")


def _check_source(source: object, entry_id: str) -> None:
    _check_keys(source, _SOURCE_KEYS, f"{entry_id} source")
    for field in ("source_id", "title", "organization", "how_checked"):
        _require(_is_text(source[field]), f"{entry_id} source: empty {field}")
    _require(isinstance(source["url"], str) and source["url"].startswith("https://"),
             f"{entry_id} source: url must be https")
    for field in ("page_date", "last_reviewed", "next_review_due"):
        _require(source[field] is None or _is_date(source[field]), f"{entry_id} source: bad {field}")
    _require(_is_date(source["checked_on"]), f"{entry_id} source: bad checked_on")
    # A passed review date must stay on record; it cannot be dropped or hidden.
    due = source["next_review_due"]
    overdue = due is not None and due < source["checked_on"]
    _require(source["review_overdue_when_checked"] is overdue, f"{entry_id} source: overdue flag is wrong")


def _check_statements(entry: dict, source_ids: set[str]) -> None:
    entry_id = entry["entry_id"]
    _require(isinstance(entry["statements"], list) and bool(entry["statements"]), f"{entry_id}: no statements")
    shown_text = "\n".join([entry["title"], *entry["paragraphs"]])
    cited = set()
    for statement in entry["statements"]:
        _check_keys(statement, _STATEMENT_KEYS, f"{entry_id} statement")
        _require(_is_text(statement["text"]) and statement["text"] in shown_text,
                 f"{entry_id}: statement is not in the answer")
        _require(isinstance(statement["evidence"], list) and bool(statement["evidence"]),
                 f"{entry_id}: statement without evidence")
        for evidence in statement["evidence"]:
            _check_keys(evidence, _EVIDENCE_KEYS, f"{entry_id} evidence")
            _require(evidence["source_id"] in source_ids, f"{entry_id}: evidence cites an unknown source")
            _require(_is_text(evidence["section"]) and _is_text(evidence["quote"]), f"{entry_id}: empty evidence")
            cited.add(evidence["source_id"])
    _require(cited == source_ids, f"{entry_id}: a listed source supports no statement")


def _check_entry(entry: object) -> None:
    _check_keys(entry, _ENTRY_KEYS, "entry")
    entry_id = entry["entry_id"]
    _require(isinstance(entry_id, str) and bool(_ENTRY_ID.fullmatch(entry_id)), "entry: malformed entry_id")
    _require(isinstance(entry["topic_id"], str) and bool(_TOPIC_ID.fullmatch(entry["topic_id"])),
             f"{entry_id}: malformed topic_id")
    _require(_is_text(entry["title"]), f"{entry_id}: empty title")
    paragraphs = entry["paragraphs"]
    _require(isinstance(paragraphs, list) and 1 <= len(paragraphs) <= MAX_PARAGRAPHS
             and all(_is_text(p) for p in paragraphs), f"{entry_id}: bad paragraphs")
    questions = entry["approved_questions"]
    _require(isinstance(questions, list) and bool(questions) and all(_is_text(q) for q in questions),
             f"{entry_id}: bad approved_questions")
    keys = [normalize_question(q) for q in questions]
    _require(len(set(keys)) == len(keys), f"{entry_id}: duplicate approved question")

    review = entry["review"]
    _check_keys(review, _REVIEW_KEYS, f"{entry_id} review")
    _require(review["review_status"] in REVIEW_STATUSES, f"{entry_id}: unknown review_status")
    _require(review["clinical_review"] == CLINICAL_REVIEW, f"{entry_id}: clinical_review must stay {CLINICAL_REVIEW}")
    _require(_is_text(review["reviewer"]) and _is_text(review["note"]), f"{entry_id}: incomplete review record")
    _require(_is_date(review["reviewed_on"]), f"{entry_id}: bad reviewed_on")

    sources = entry["sources"]
    _require(isinstance(sources, list) and bool(sources), f"{entry_id}: no sources")
    for source in sources:
        _check_source(source, entry_id)
    source_ids = [s["source_id"] for s in sources]
    _require(len(set(source_ids)) == len(source_ids), f"{entry_id}: duplicate source_id")
    _check_statements(entry, set(source_ids))


def validate(content: object) -> None:
    """Raise KnowledgeError unless the parsed content file meets every rule."""
    _check_keys(content, _TOP_KEYS, "content file")
    _require(content["knowledge_version"] == KNOWLEDGE_VERSION, "content file: unexpected knowledge_version")
    entries = content["entries"]
    _require(isinstance(entries, list) and bool(entries), "content file: no entries")
    for entry in entries:
        _check_entry(entry)
    ids = [e["entry_id"] for e in entries]
    _require(len(set(ids)) == len(ids), "content file: duplicate entry_id")
    keys = [normalize_question(q) for e in entries for q in e["approved_questions"]]
    _require(len(set(keys)) == len(keys), "content file: a question belongs to two entries")


def load_entries(path: Path = CONTENT_FILE) -> tuple[Entry, ...]:
    """Read and validate the content file. Raises on any problem."""
    content = json.loads(path.read_text(encoding="utf-8"))
    validate(content)
    return tuple(
        Entry(
            entry_id=e["entry_id"],
            topic_id=e["topic_id"],
            title=e["title"],
            paragraphs=tuple(e["paragraphs"]),
            sources=tuple(Source(s["title"], s["organization"], s["url"]) for s in e["sources"]),
            review_status=e["review"]["review_status"],
            question_keys=frozenset(normalize_question(q) for q in e["approved_questions"]),
        )
        for e in content["entries"]
    )


def _load_at_import() -> tuple[Entry, ...] | None:
    try:
        return load_entries()
    except Exception as exc:  # noqa: BLE001 - reported as unavailable, so the pipeline fails closed
        logger.error("Curated knowledge unavailable (%s)", type(exc).__name__)
        return None


_ENTRIES = _load_at_import()


def is_available() -> bool:
    return _ENTRIES is not None


def retrieve(question: str) -> Entry | None:
    """The displayable entry approved for this exact question, or None."""
    if _ENTRIES is None:
        raise KnowledgeUnavailable("curated knowledge could not be loaded")
    key = normalize_question(question)
    for entry in _ENTRIES:
        if key in entry.question_keys and entry.review_status == DISPLAYABLE_REVIEW_STATUS:
            return entry
    return None
