"""Curated topic catalogue, topic examples, and validation topic labels (D-15).

The catalogue lists educational topics only. It contains no medical answers
and no dataset text. Topic examples are assistant-generated synthetic questions
pending owner review. Topic matching (not built yet) decides relevance only; it
never decides safety, scope, or permission to display.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from querymate import audit, config

CURATED_DIR = config.PROJECT_ROOT / "curated"
TOPICS_FILE = CURATED_DIR / "topics.csv"
EXAMPLES_FILE = CURATED_DIR / "topic_examples.csv"
VALIDATION_LABELS_FILE = config.EVAL_DIR / "validation_topic_labels.csv"

TOPIC_COLUMNS = ["topic_id", "topic_name", "domain", "scope_status", "description",
                 "exclusions", "author", "created_date", "version"]
TOPIC_ID = re.compile(r"TOP-\d{3}")
DOMAINS = {"prevention", "condition_overview", "health_literacy"}
SCOPE_STATUSES = {"in_scope"}  # deferred topics are kept out of this prototype (D-15)
TOPIC_TEXT_FIELDS = ["topic_name", "description", "exclusions"]

# The provisionally approved catalogue (D-15).
APPROVED_TOPIC_IDS = {
    "TOP-001", "TOP-002", "TOP-003", "TOP-004", "TOP-005", "TOP-006", "TOP-007", "TOP-008",
    "TOP-101", "TOP-102", "TOP-103", "TOP-104", "TOP-105", "TOP-106", "TOP-107", "TOP-108",
    "TOP-109", "TOP-110", "TOP-201", "TOP-202",
}

EXAMPLE_COLUMNS = ["example_id", "topic_id", "topic_name", "example_question", "example_type",
                   "author", "created_date", "provenance", "review_status"]
EXAMPLE_ID = re.compile(r"EX-\d{4}")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
EXAMPLES_PER_TOPIC = 6
EXAMPLE_TYPE_COUNTS = {"canonical": 2, "paraphrase": 2, "lay_term": 2}  # per topic
EXAMPLE_AUTHOR = "assistant"  # AI-assisted; not written by the owner (D-15(b), amended)
EXAMPLE_PROVENANCES = {
    "assistant-generated, synthetic",
    "assistant-generated, synthetic; rewritten to reduce evaluation overlap",
}
EXAMPLE_REVIEW_STATUSES = {"pending_owner_review", "owner_approved"}

# Leakage detection between topic examples and the evaluation sets. The Test set is
# read here only to detect copies; it is never used for matching, tuning, topic
# selection, or rewriting examples (D-09, D-15). Thresholds and stopwords are the
# same uncalibrated values as scripts/check_eval_sets.py, fixed before any results
# were seen. Lexical only: same-meaning questions in different words are not caught.
EVAL_FILES = {"validation": config.EVAL_DIR / "validation_questions.csv",
              "test": config.EVAL_DIR / "test_questions.csv"}
OVERLAP_CHAR_COSINE = 0.5   # character 3-5-gram TF-IDF cosine
OVERLAP_WORD_JACCARD = 0.5  # content-word Jaccard
OVERLAP_STOPWORDS = {"a", "an", "the", "is", "are", "my", "i", "to", "of", "and", "for", "what",
                     "it", "in", "do", "does", "can", "you", "me", "with", "how", "should", "if",
                     "this", "that"}

# Review flag only, not safety detection or triage, and not clinically validated.
# It marks examples whose wording may look like an emergency or crisis message so the
# owner can check them; flagged examples are never rewritten automatically. Uses the
# audit's emergency keyword patterns plus a few explicit urgency/crisis phrases.
EMERGENCY_REVIEW_EXTRA = {
    "urgent_help_terms": r"\bemergenc\w*|\bambulance\b|\b(?:911|999|112)\b|\burgent\w*",
    "crisis_terms": (r"\bwant(?:s|ed)? to die\b|\bhurt(?:ing)? (?:my|him|her|them)sel(?:f|ves)\b"
                     r"|\btook too many\b|\bwhole bottle\b"),
    "collapse_terms": r"\bcollaps\w*|\bunresponsive\b|\bnot breathing\b|\bblue lips\b",
    "sudden_severe_terms": r"\bsudden(?:ly)? (?:and )?severe\b|\bworst headache\b",
}
_EMERGENCY_REVIEW_EXTRA = {k: re.compile(p, re.IGNORECASE) for k, p in EMERGENCY_REVIEW_EXTRA.items()}

LABEL_COLUMNS =["question_id", "suggested_topic_id", "related_topic_ids", "label_use",
                 "review_status", "rationale"]
NO_TOPIC = "NONE"
LABEL_USES = {"graded", "risk_indicator_only"}
REVIEW_STATUSES = {"draft_pending_owner_review", "owner_approved"}
POLICY_ROUTED_CATEGORIES = {"emergency", "diagnosis_request", "medication_dosage", "safe_fallback"}

# Wording that must never appear in catalogue text: dataset artefacts, dosing,
# prescribing, a doctor persona, or diagnostic certainty.
_FORBIDDEN_FLAGS = [
    ("placeholders", "chat_doctor_token_any"),
    ("medical_risk_indicators", "dose_amount"),
    ("medical_risk_indicators", "dosing_frequency"),
    ("medical_risk_indicators", "prescribing_language"),
    ("medical_risk_indicators", "doctor_persona_language"),
    ("medical_risk_indicators", "diagnostic_certainty_language"),
]
SHINGLE_WORDS = 8


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def load_topics(path: Path = TOPICS_FILE) -> pd.DataFrame:
    return _read(path)


def load_topic_examples(path: Path = EXAMPLES_FILE) -> pd.DataFrame:
    return _read(path)


def load_validation_labels(path: Path = VALIDATION_LABELS_FILE) -> pd.DataFrame:
    return _read(path)


def privacy_wording(text: str) -> list[str]:
    """Names of audit privacy patterns found in `text`."""
    return [name for name, (rx, use_lower) in audit._COMPILED["privacy_indicators"].items()
            if rx.search(text.lower() if use_lower else text)]


def forbidden_wording(text: str) -> list[str]:
    """Names of forbidden audit patterns found in `text`."""
    hits = []
    for group, name in _FORBIDDEN_FLAGS:
        rx, use_lower = audit._COMPILED[group][name]
        if rx.search(text.lower() if use_lower else text):
            hits.append(name)
    return hits


def validate_topics(df: pd.DataFrame) -> list[str]:
    problems = []
    if list(df.columns) != TOPIC_COLUMNS:
        return [f"columns {list(df.columns)} != {TOPIC_COLUMNS}"]
    for col in TOPIC_COLUMNS:
        if (df[col].str.strip() == "").any():
            problems.append(f"empty values in {col}")
    if not df["topic_id"].map(lambda v: bool(TOPIC_ID.fullmatch(v))).all():
        problems.append("malformed topic_id")
    if df["topic_id"].duplicated().any():
        problems.append("duplicate topic_id")
    if df["topic_name"].str.lower().duplicated().any():
        problems.append("duplicate topic_name")
    if set(df["topic_id"]) != APPROVED_TOPIC_IDS:
        problems.append("topic_id set differs from the approved catalogue (D-15)")
    if bad := set(df["domain"]) - DOMAINS:
        problems.append(f"unknown domain {bad}")
    if bad := set(df["scope_status"]) - SCOPE_STATUSES:
        problems.append(f"scope_status not allowed in this prototype {bad}")
    for row in df.itertuples(index=False):
        for field in TOPIC_TEXT_FIELDS:
            if hits := forbidden_wording(getattr(row, field)):
                problems.append(f"{row.topic_id}.{field}: forbidden wording {hits}")
    return problems


def validate_topic_examples(df: pd.DataFrame, topics: pd.DataFrame) -> list[str]:
    """Problems with the topic examples. Messages name example IDs only, never question text."""
    if list(df.columns) != EXAMPLE_COLUMNS:
        return [f"columns {list(df.columns)} != {EXAMPLE_COLUMNS}"]
    problems = []
    for col in EXAMPLE_COLUMNS:
        if (df[col].str.strip() == "").any():
            problems.append(f"empty values in {col}")
        if (df[col] != df[col].str.strip()).any():
            problems.append(f"leading or trailing whitespace in {col}")
    if not df["example_id"].map(lambda v: bool(EXAMPLE_ID.fullmatch(v))).all():
        problems.append("malformed example_id")
    if list(df["example_id"]) != [f"EX-{i:04d}" for i in range(1, len(df) + 1)]:
        problems.append("example_id values are not unique and sequential from EX-0001")

    names = dict(zip(topics["topic_id"], topics["topic_name"]))
    if bad := set(df["topic_id"]) - set(names):
        problems.append(f"unknown topic_id {sorted(bad)}")
    if missing := set(names) - set(df["topic_id"]):
        problems.append(f"topics without examples {sorted(missing)}")
    wrong_name = df["topic_id"].isin(set(names)) & (df["topic_name"] != df["topic_id"].map(names))
    problems += [f"{e}: topic_name differs from curated/topics.csv" for e in df.loc[wrong_name, "example_id"]]

    if bad := set(df["example_type"]) - set(EXAMPLE_TYPE_COUNTS):
        problems.append(f"unknown example_type {sorted(bad)}")
    for topic_id, group in df.groupby("topic_id"):
        if len(group) != EXAMPLES_PER_TOPIC:
            problems.append(f"{topic_id}: {len(group)} examples, expected {EXAMPLES_PER_TOPIC}")
        if group["example_type"].value_counts().to_dict() != EXAMPLE_TYPE_COUNTS:
            problems.append(f"{topic_id}: example_type counts differ from {EXAMPLE_TYPE_COUNTS}")

    for e in df.loc[df["author"] != EXAMPLE_AUTHOR, "example_id"]:
        problems.append(f"{e}: author must be '{EXAMPLE_AUTHOR}' (assistant-generated)")
    for e in df.loc[~df["provenance"].isin(EXAMPLE_PROVENANCES), "example_id"]:
        problems.append(f"{e}: provenance must record assistant-generated synthetic origin")
    if bad := set(df["review_status"]) - EXAMPLE_REVIEW_STATUSES:
        problems.append(f"unknown review_status {sorted(bad)}")
    if not df["created_date"].map(lambda v: bool(ISO_DATE.fullmatch(v))).all():
        problems.append("created_date not in YYYY-MM-DD format")

    norm = df["example_question"].map(audit.normalize_question)
    problems += [f"{e}: duplicate example_question" for e in df.loc[norm.duplicated(), "example_id"]]
    for row in df.itertuples(index=False):
        if hits := forbidden_wording(row.example_question):
            problems.append(f"{row.example_id}: forbidden wording {hits}")
        if hits := privacy_wording(row.example_question):
            problems.append(f"{row.example_id}: privacy pattern {hits}")
    return problems


def validate_labels(labels: pd.DataFrame, validation: pd.DataFrame, topic_ids: set[str]) -> list[str]:
    problems = []
    if list(labels.columns) != LABEL_COLUMNS:
        return [f"columns {list(labels.columns)} != {LABEL_COLUMNS}"]
    if labels["question_id"].duplicated().any():
        problems.append("duplicate question_id")
    if list(labels["question_id"]) != list(validation["question_id"]):
        problems.append("question_id list differs from the validation set (order or membership)")
    valid = topic_ids | {NO_TOPIC}
    if bad := set(labels["suggested_topic_id"]) - valid:
        problems.append(f"unknown suggested_topic_id {bad}")
    for qid, rel in zip(labels["question_id"], labels["related_topic_ids"]):
        if rel and (bad := set(rel.split(";")) - topic_ids):
            problems.append(f"{qid}: unknown related_topic_ids {bad}")
    if bad := set(labels["label_use"]) - LABEL_USES:
        problems.append(f"unknown label_use {bad}")
    if bad := set(labels["review_status"]) - REVIEW_STATUSES:
        problems.append(f"unknown review_status {bad}")
    if (labels["rationale"].str.strip() == "").any():
        problems.append("empty rationale")
    cats = dict(zip(validation["question_id"], validation["category"]))
    for row in labels.itertuples(index=False):
        policy = cats.get(row.question_id) in POLICY_ROUTED_CATEGORIES
        if policy and row.label_use != "risk_indicator_only":
            problems.append(f"{row.question_id}: policy-routed question must be risk_indicator_only")
        if not policy and row.label_use != "graded":
            problems.append(f"{row.question_id}: non-policy question must be graded")
        if policy and row.suggested_topic_id != NO_TOPIC:
            problems.append(f"{row.question_id}: policy-routed question must have suggested_topic_id NONE")
    question_texts = set(validation["question"])
    if any(t in question_texts for t in labels["rationale"]):
        problems.append("rationale copies a validation question")
    return problems


def _shingles(text: str, n: int = SHINGLE_WORDS) -> set[str]:
    words = audit.normalize_question(text).split()
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def dataset_text_overlap(texts, dataset_texts, n: int = SHINGLE_WORDS) -> int:
    """Count dataset texts sharing any n-word sequence with `texts` (copy detection)."""
    target = set().union(*(_shingles(t, n) for t in texts)) if texts else set()
    if not target:
        return 0
    hits = 0
    for d in dataset_texts:
        words = audit.normalize_question(d).split()
        if any(" ".join(words[i:i + n]) in target for i in range(len(words) - n + 1)):
            hits += 1
    return hits


def dataset_copy_ids(texts_by_id: dict[str, str], dataset_texts, n: int = SHINGLE_WORDS) -> list[str]:
    """IDs whose text shares an n-word sequence with any dataset text.

    Returns IDs only, so callers never print dataset or example text (D-01, D-14).
    """
    owners: dict[str, set[str]] = {}
    for key, text in texts_by_id.items():
        for s in _shingles(text, n):
            owners.setdefault(s, set()).add(key)
    if not owners:
        return []
    found: set[str] = set()
    for d in dataset_texts:
        words = audit.normalize_question(d).split()
        for i in range(len(words) - n + 1):
            found |= owners.get(" ".join(words[i:i + n]), set())
    return sorted(found)


def dataset_question_matches(texts_by_id: dict[str, str], dataset_norm_keys) -> list[str]:
    """IDs whose normalised text exactly equals a dataset question (IDs only)."""
    keys = set(dataset_norm_keys)
    return sorted(k for k, t in texts_by_id.items() if audit.normalize_question(t) in keys)


# --- Evaluation-set leakage detection ----------------------------------------------

def load_eval_questions_for_leakage_check() -> pd.DataFrame:
    """`question_id` and `question` from both evaluation sets, for leakage detection only.

    Not for matching, tuning, threshold or topic selection, or rewriting examples
    (D-09, D-15). Categories, behaviours, and rationales are deliberately dropped.
    """
    return pd.concat([_read(p)[["question_id", "question"]] for p in EVAL_FILES.values()],
                     ignore_index=True)


def _content_words(text: str) -> set[str]:
    return {w for w in audit.normalize_question(text).split() if w not in OVERLAP_STOPWORDS}


def eval_set_overlap(examples: pd.DataFrame, eval_questions: pd.DataFrame) -> list[tuple]:
    """Exact and near-duplicate pairs between topic examples and evaluation questions.

    Returns sorted tuples `(kind, example_id, question_id, char_cosine, word_jaccard)`
    with kind "exact" (same normalised text) or "near" (cosine >= OVERLAP_CHAR_COSINE
    or Jaccard >= OVERLAP_WORD_JACCARD). IDs and scores only, never question text.
    Passing this check does not show independence: conceptual overlap may remain.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    ex_text, ev_text = list(examples["example_question"]), list(eval_questions["question"])
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), lowercase=True)
    vec.fit(ex_text + ev_text)
    sim = cosine_similarity(vec.transform(ex_text), vec.transform(ev_text))
    ex_norm = [audit.normalize_question(t) for t in ex_text]
    ev_norm = [audit.normalize_question(t) for t in ev_text]
    ex_words = [_content_words(t) for t in ex_text]
    ev_words = [_content_words(t) for t in ev_text]

    pairs = []
    for i, ex_id in enumerate(examples["example_id"]):
        for j, q_id in enumerate(eval_questions["question_id"]):
            union = ex_words[i] | ev_words[j]
            jac = len(ex_words[i] & ev_words[j]) / len(union) if union else 0.0
            cos = float(sim[i, j])
            if ex_norm[i] == ev_norm[j]:
                kind = "exact"
            elif cos >= OVERLAP_CHAR_COSINE or jac >= OVERLAP_WORD_JACCARD:
                kind = "near"
            else:
                continue
            pairs.append((kind, ex_id, q_id, round(cos, 2), round(jac, 2)))
    return sorted(pairs)


# --- Emergency/crisis wording review flag -------------------------------------------

def emergency_review_flags(examples: pd.DataFrame) -> list[tuple[str, list[str]]]:
    """`(example_id, pattern_names)` for examples to check manually (IDs only).

    A conservative keyword heuristic for review, not safety detection, triage, or
    clinical validation. Unflagged examples are not shown to be safe. Never rewrites.
    """
    flags = []
    for ex_id, text in zip(examples["example_id"], examples["example_question"]):
        hits = [name for name, (rx, use_lower) in audit._COMPILED["emergency_related_questions"].items()
                if rx.search(text.lower() if use_lower else text)]
        hits += [name for name, rx in _EMERGENCY_REVIEW_EXTRA.items() if rx.search(text)]
        if hits:
            flags.append((ex_id, hits))
    return flags
