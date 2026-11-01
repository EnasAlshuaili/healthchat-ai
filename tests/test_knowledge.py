"""Curated knowledge entries and deterministic retrieval (Phase D, curated/topic_content.json).

The entry is owner-reviewed educational content. These tests check its structure and
the lookup rules; they do not show that it is medically accurate.
"""

import ast
import copy
import json
import logging
import subprocess
import sys

import pandas as pd
import pytest

from querymate import config, curated, knowledge, safety
from querymate.safety import Route

APPROVED_ANSWER = (
    "Why staying hydrated matters",
    (
        "Water helps your body keep a normal temperature, lubricates and cushions your joints, and helps get "
        "rid of waste through urination, sweating, and bowel movements.",
        "Not getting enough fluid can lead to dehydration.",
        "You may need more fluid in hot weather, during physical activity, or when you are ill. Recommended "
        "daily water intake varies, for example by age, sex, and activity level.",
        "This is general educational content reviewed by the project owner. It has not been clinically "
        "reviewed or clinically validated. For personal advice, consult a qualified healthcare professional. "
        "If you think you may be experiencing an emergency, contact local emergency services immediately.",
    ),
)
APPROVED_SOURCES = [
    ("About Water and Healthier Drinks", "Centers for Disease Control and Prevention (CDC)",
     "https://www.cdc.gov/healthy-weight-growth/water-healthy-drinks/"),
    ("Water, drinks and hydration", "NHS",
     "https://www.nhs.uk/Live-well/eat-well/food-guidelines-and-food-labels/water-drinks-nutrition/"),
    ("Dehydration", "NHS", "https://www.nhs.uk/conditions/dehydration/"),
]
APPROVED_QUESTIONS = [
    "Why is staying hydrated important?",
    "Why is hydration important?",
    "Why is it important to stay hydrated?",
    "Why is staying hydrated important for the body?",
    "Why does the body need water?",
    "Why do we need to drink water?",
]
# Wordings the router sends to PROCEED that the general answer must not cover.
NOT_COVERED = [
    "Why is staying hydrated important for babies?",
    "Why is staying hydrated important during pregnancy?",
    "Why is staying hydrated important for my kidneys?",
    "Why is staying hydrated important for diabetes?",
    "Why is staying hydrated important when I have diarrhoea?",
    "Why is staying hydrated important? I feel dizzy and confused",
    "Why is staying hydrated important? Also what is cholesterol?",
    "Why is staying hydrated not important?",
    "Does staying hydrated cure kidney stones?",
    "My baby is dehydrated",
    "Should I stop drinking water?",
    "What are the signs of dehydration?",
]
UNRELATED = ["What is LDL cholesterol?", "Why is sleep important?", "What is fibre?", "hydration", "water"]


@pytest.fixture
def content():
    return json.loads(knowledge.CONTENT_FILE.read_text(encoding="utf-8"))


def write(tmp_path, content):
    path = tmp_path / "content.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


def source(content, source_id):
    return next(s for s in content["entries"][0]["sources"] if s["source_id"] == source_id)


# --- Relevant matching --------------------------------------------------------------------------

@pytest.mark.parametrize("question", APPROVED_QUESTIONS)
def test_approved_questions_return_the_entry(question):
    assert knowledge.retrieve(question).entry_id == "KN-0001"


@pytest.mark.parametrize("question", APPROVED_QUESTIONS)
def test_approved_questions_all_pass_the_router(question):
    assert safety.route(question).route is Route.PROCEED


@pytest.mark.parametrize("question", [
    "why is staying hydrated important", "WHY IS STAYING HYDRATED IMPORTANT?",
    "  Why   is staying\nhydrated important ?!  ", "Why is staying hydrated important？",
], ids=["lower", "upper", "spacing", "fullwidth"])
def test_case_punctuation_and_spacing_do_not_matter(question):
    assert knowledge.retrieve(question).entry_id == "KN-0001"


def test_normalising_never_removes_words():
    assert knowledge.normalize_question("Why is it, really?") == "why is it really"
    assert knowledge.normalize_question("not_important") == "not important"


# --- Unrelated and uncovered questions -----------------------------------------------------------

@pytest.mark.parametrize("question", UNRELATED)
def test_unrelated_questions_return_nothing(question):
    assert knowledge.retrieve(question) is None


@pytest.mark.parametrize("question", NOT_COVERED)
def test_router_proceeds_but_the_general_answer_does_not_match(question):
    assert safety.route(question).route is Route.PROCEED  # so retrieval is the check that stops these
    assert knowledge.retrieve(question) is None


@pytest.mark.parametrize("question", ["", "   ", "?!", "...."])
def test_empty_text_returns_nothing(question):
    assert knowledge.retrieve(question) is None


# --- The approved entry and its source metadata -----------------------------------------------------

def test_answer_is_exactly_the_owner_approved_text():
    entry = knowledge.retrieve(APPROVED_QUESTIONS[0])
    assert (entry.title, entry.paragraphs) == APPROVED_ANSWER


def test_sources_are_exactly_the_approved_references():
    entry = knowledge.retrieve(APPROVED_QUESTIONS[0])
    assert [(s.title, s.organization, s.url) for s in entry.sources] == APPROVED_SOURCES


def test_review_record_is_owner_review_and_not_clinical(content):
    review = content["entries"][0]["review"]
    assert review["review_status"] == "owner_reviewed"
    assert review["clinical_review"] == "not_clinically_reviewed"
    assert review["reviewer"] == "project owner" and review["reviewed_on"] == "2026-10-31"
    assert "Not clinical review or medical validation" in review["note"]
    assert knowledge.retrieve(APPROVED_QUESTIONS[0]).review_status == "owner_reviewed"


def test_answer_makes_no_clinical_claim():
    text = " ".join(APPROVED_ANSWER[1]).lower()
    assert "has not been clinically reviewed or clinically validated" in text
    remainder = text.replace("has not been clinically reviewed or clinically validated", "")
    for claim in ("clinically", "medically", "verified", "approved", "validated"):
        assert claim not in remainder


def test_nhs_water_page_overdue_review_date_is_recorded(content):
    nhs = source(content, "nhs_water")
    assert (nhs["last_reviewed"], nhs["next_review_due"]) == ("2023-05-17", "2026-05-17")
    assert nhs["review_overdue_when_checked"] is True
    assert source(content, "nhs_dehydration")["review_overdue_when_checked"] is False


def test_every_statement_has_evidence_from_a_listed_source(content):
    entry = content["entries"][0]
    ids = {s["source_id"] for s in entry["sources"]}
    assert len(entry["statements"]) == 7
    for statement in entry["statements"]:
        assert statement["evidence"]
        assert {e["source_id"] for e in statement["evidence"]} <= ids


def test_entry_links_to_the_hydration_topic():
    assert knowledge.retrieve(APPROVED_QUESTIONS[0]).topic_id == "TOP-001"
    assert "TOP-001" in set(curated.load_topics()["topic_id"])


def test_entry_is_the_only_one_in_this_scope(content):
    assert len(content["entries"]) == 1


def test_answer_has_no_dataset_artefacts_or_dosing_wording():
    for text in (APPROVED_ANSWER[0], *APPROVED_ANSWER[1]):
        assert curated.forbidden_wording(text) == []
        assert curated.privacy_wording(text) == []


@pytest.mark.skipif(not (config.PROCESSED_DIR / "querymate_clean.parquet").exists(),
                    reason="processed dataset not present")
def test_answer_shares_no_text_with_the_dataset():
    d = pd.read_parquet(config.PROCESSED_DIR / "querymate_clean.parquet", columns=["question", "answer"])
    texts = [APPROVED_ANSWER[0], *APPROVED_ANSWER[1]]
    assert curated.dataset_text_overlap(texts, d["answer"]) == 0
    assert curated.dataset_text_overlap(texts, d["question"]) == 0


# --- Display rule and validation ----------------------------------------------------------------

def test_pending_entry_loads_but_is_never_retrieved(content, tmp_path, monkeypatch):
    content["entries"][0]["review"]["review_status"] = "pending_owner_review"
    entries = knowledge.load_entries(write(tmp_path, content))
    monkeypatch.setattr(knowledge, "_ENTRIES", entries)
    assert knowledge.retrieve(APPROVED_QUESTIONS[0]) is None


def _set(path, value):
    def change(content):
        target = content["entries"][0]
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value
    return change


def _source_field(source_id, field, value):
    return lambda content: source(content, source_id).__setitem__(field, value)


@pytest.mark.parametrize("change", [
    _set(["review", "clinical_review"], "clinically_reviewed"),
    _set(["review", "review_status"], "clinically_reviewed"),
    _set(["review", "reviewed_on"], "31 October 2026"),
    _set(["sources"], []),
    _set(["statements"], []),
    _set(["paragraphs"], []),
    _set(["paragraphs"], ["text"] * 6),
    _set(["approved_questions"], []),
    _set(["approved_questions"], ["Why is hydration important?", "why is hydration important"]),
    _set(["title"], " "),
    _set(["entry_id"], "KN-1"),
    _set(["extra"], 1),
    _source_field("nhs_water", "url", "http://www.nhs.uk/"),
    _source_field("nhs_water", "url", "javascript:alert(1)"),
    _source_field("nhs_water", "review_overdue_when_checked", False),
    _source_field("nhs_water", "organization", ""),
    lambda c: c["entries"][0]["sources"].append(copy.deepcopy(c["entries"][0]["sources"][0])),
    lambda c: c["entries"][0]["sources"][0].pop("how_checked"),
    lambda c: c["entries"][0]["statements"][1].__setitem__("evidence", []),
    lambda c: c["entries"][0]["statements"][1].__setitem__("text", "Water cures everything"),
    lambda c: c["entries"][0]["statements"][1]["evidence"][0].__setitem__("source_id", "unknown"),
    lambda c: c["entries"].append(copy.deepcopy(c["entries"][0])),
    lambda c: c.__setitem__("knowledge_version", "9.9.9"),
    lambda c: c.__setitem__("entries", []),
], ids=["clinical_claim", "unknown_status", "bad_date", "no_sources", "no_statements", "no_paragraphs",
        "too_many_paragraphs", "no_questions", "duplicate_question", "blank_title", "bad_id", "extra_field",
        "http_url", "script_url", "hidden_overdue_date", "blank_organization", "duplicate_source",
        "missing_source_field", "no_evidence", "statement_not_in_answer", "unknown_evidence_source",
        "duplicate_entry", "wrong_version", "no_entries"])
def test_invalid_content_is_rejected(content, change):
    change(content)
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.validate(content)


def test_source_that_supports_no_statement_is_rejected(content):
    for statement in content["entries"][0]["statements"]:
        statement["evidence"] = [e for e in statement["evidence"] if e["source_id"] != "nhs_dehydration"]
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.validate(content)


# --- Missing knowledge ------------------------------------------------------------------------------

def test_retrieve_raises_when_knowledge_is_unavailable(monkeypatch):
    monkeypatch.setattr(knowledge, "_ENTRIES", None)
    assert knowledge.is_available() is False
    with pytest.raises(knowledge.KnowledgeUnavailable):
        knowledge.retrieve(APPROVED_QUESTIONS[0])


@pytest.mark.parametrize("text", ["{not json", "[]", '{"knowledge_version": "0.1.0", "entries": []}'],
                         ids=["malformed", "wrong_shape", "empty"])
def test_broken_file_is_reported_without_details(text, tmp_path, monkeypatch, caplog):
    path = tmp_path / "broken.json"
    path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(knowledge.load_entries, "__defaults__", (path,))
    with caplog.at_level(logging.ERROR, logger="querymate.knowledge"):
        assert knowledge._load_at_import() is None
    assert "Curated knowledge unavailable" in caplog.text and str(tmp_path) not in caplog.text


def test_missing_file_is_reported_as_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge.load_entries, "__defaults__", (tmp_path / "absent.json",))
    assert knowledge._load_at_import() is None


# --- Separation --------------------------------------------------------------------------------------

def test_module_imports_no_dataset_matcher_or_network_code():
    tree = ast.parse((config.PROJECT_ROOT / "src" / "querymate" / "knowledge.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.update(f"{node.module}.{a.name}" for a in node.names)
    assert imported == {"__future__.annotations", "json", "logging", "re", "unicodedata",
                        "dataclasses.dataclass", "datetime.date", "pathlib.Path", "querymate.config"}


def test_importing_the_module_loads_no_dataset_or_matcher_code():
    code = ("import sys; sys.path.insert(0, 'src'); import querymate.knowledge; "
            "print(sorted(m for m in sys.modules if m in {'querymate.topic_matcher', 'querymate.retrieval', "
            "'querymate.curated', 'querymate.cleaning', 'pandas'} or m.split('.')[0] == 'sklearn'))")
    out = subprocess.run([sys.executable, "-c", code], cwd=config.PROJECT_ROOT,
                         capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"


def test_retrieval_opens_no_files_and_logs_nothing(monkeypatch, caplog):
    def forbidden(*_a, **_k):
        raise AssertionError("retrieval must not read a file")
    monkeypatch.setattr(knowledge.Path, "read_text", forbidden)
    with caplog.at_level(logging.DEBUG, logger="querymate.knowledge"):
        assert knowledge.retrieve(APPROVED_QUESTIONS[0]) is not None
        assert knowledge.retrieve("What is fibre?") is None
    assert caplog.records == []
