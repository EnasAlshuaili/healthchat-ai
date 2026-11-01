"""Tests for the curated topic catalogue, topic examples, and validation topic labels (D-15)."""

import pandas as pd
import pytest

from querymate import config, curated, retrieval_eval


@pytest.fixture(scope="module")
def topics():
    return curated.load_topics()


@pytest.fixture(scope="module")
def labels():
    return curated.load_validation_labels()


@pytest.fixture(scope="module")
def validation():
    return retrieval_eval.load_validation()  # validation only; refuses the test set


# --- Catalogue ------------------------------------------------------------------

def test_catalogue_is_valid(topics):
    assert curated.validate_topics(topics) == []


def test_catalogue_has_20_unique_in_scope_topics(topics):
    assert len(topics) == 20
    assert topics["topic_id"].is_unique
    assert set(topics["scope_status"]) == {"in_scope"}
    assert set(topics["topic_id"]) == curated.APPROVED_TOPIC_IDS


def test_catalogue_has_no_answer_or_example_columns(topics):
    forbidden = {"answer", "output", "body", "example_question", "source_row", "display_allowed"}
    assert not forbidden & set(topics.columns)


def test_validator_catches_schema_and_id_problems(topics):
    bad = topics.copy()
    bad.loc[1, "topic_id"] = bad.loc[0, "topic_id"]
    assert any("duplicate topic_id" in p for p in curated.validate_topics(bad))
    bad = topics.copy()
    bad.loc[0, "topic_id"] = "TOPIC-1"
    assert any("malformed" in p for p in curated.validate_topics(bad))
    bad = topics.copy()
    bad.loc[0, "scope_status"] = "deferred"
    assert any("scope_status" in p for p in curated.validate_topics(bad))
    assert curated.validate_topics(topics.drop(columns=["exclusions"]))


@pytest.mark.parametrize("text, flag", [
    ("Hi, thanks for using Chat Doctor. Drink water.", "chat_doctor_token_any"),
    ("Take 500 mg each morning.", "dose_amount"),
    ("Use it twice daily.", "dosing_frequency"),
    ("Start taking these tablets now.", "prescribing_language"),
    ("I am a doctor and this is general.", "doctor_persona_language"),
])
def test_validator_rejects_dataset_artefacts_and_advice(topics, text, flag):
    assert flag in curated.forbidden_wording(text)
    bad = topics.copy()
    bad.loc[0, "description"] = text
    assert any(flag in p for p in curated.validate_topics(bad))


def test_dataset_overlap_detector():
    dataset = ["Hi thanks for the query the most likely cause is a viral infection of the throat today",
               "Completely unrelated text about something else entirely here"]
    copied = ["General info: the most likely cause is a viral infection of the throat."]
    assert curated.dataset_text_overlap(copied, dataset) == 1
    assert curated.dataset_text_overlap(["General information about sleep."], dataset) == 0


@pytest.mark.skipif(not (config.PROCESSED_DIR / "querymate_clean.parquet").exists(),
                    reason="processed dataset not present")
def test_catalogue_shares_no_text_with_dataset(topics):
    d = pd.read_parquet(config.PROCESSED_DIR / "querymate_clean.parquet",
                        columns=["question", "answer", "display_allowed"])
    texts = [t for f in curated.TOPIC_TEXT_FIELDS for t in topics[f]]
    assert curated.dataset_text_overlap(texts, d["answer"]) == 0
    assert curated.dataset_text_overlap(texts, d["question"]) == 0
    assert not d["display_allowed"].any()


# --- Topic examples ----------------------------------------------------------------

@pytest.fixture(scope="module")
def examples():
    return curated.load_topic_examples()


def _problems(df, topics):
    return curated.validate_topic_examples(df, topics)


def test_examples_are_valid(examples, topics):
    assert _problems(examples, topics) == []


def test_examples_have_120_rows_6_per_topic(examples, topics):
    assert len(examples) == 120
    assert examples["example_id"].is_unique
    assert set(examples["topic_id"]) == set(topics["topic_id"])
    assert set(examples["topic_id"].value_counts()) == {6}
    assert examples["example_type"].value_counts().to_dict() == {
        "canonical": 40, "paraphrase": 40, "lay_term": 40}


def test_examples_are_marked_assistant_generated_and_pending_review(examples):
    # D-15(b), amended: AI-assisted, not written by the owner, not yet reviewed.
    assert set(examples["author"]) == {"assistant"}
    assert examples["provenance"].str.startswith("assistant-generated, synthetic").all()
    assert set(examples["review_status"]) == {"pending_owner_review"}
    assert set(examples["provenance"]) <= curated.EXAMPLE_PROVENANCES
    # The rewrite history is recorded per row; the number of rewritten rows is not fixed.
    rewritten = examples["provenance"].str.endswith("; rewritten to reduce evaluation overlap")
    assert rewritten.any()
    assert (examples.loc[~rewritten, "provenance"] == "assistant-generated, synthetic").all()


def test_examples_have_no_answer_or_dataset_columns(examples):
    forbidden = {"answer", "output", "body", "source_row", "display_allowed", "question_id"}
    assert not forbidden & set(examples.columns)


def test_example_validator_catches_schema_id_and_topic_problems(examples, topics):
    assert _problems(examples.drop(columns=["review_status"]), topics)
    bad = examples.copy()
    bad.loc[1, "example_id"] = bad.loc[0, "example_id"]
    assert any("sequential" in p for p in _problems(bad, topics))
    bad = examples.copy()
    bad.loc[0, "example_id"] = "EX-1"
    assert any("malformed example_id" in p for p in _problems(bad, topics))
    bad = examples.iloc[1:].reset_index(drop=True)
    assert any("sequential" in p for p in _problems(bad, topics))
    assert any("5 examples" in p for p in _problems(bad, topics))
    bad = examples.copy()
    bad.loc[0, "topic_id"] = "TOP-999"
    assert any("unknown topic_id" in p for p in _problems(bad, topics))
    bad = examples.copy()
    bad.loc[0, "topic_name"] = bad.loc[0, "topic_name"].lower()
    assert any("EX-0001: topic_name" in p for p in _problems(bad, topics))
    bad = examples[examples["topic_id"] != "TOP-202"].reset_index(drop=True)
    assert any("topics without examples ['TOP-202']" in p for p in _problems(bad, topics))


def test_example_validator_catches_type_status_and_field_problems(examples, topics):
    bad = examples.copy()
    bad.loc[0, "example_type"] = "lay_term"  # TOP-001 now has 1 canonical, 3 lay_term
    assert any("TOP-001: example_type counts" in p for p in _problems(bad, topics))
    bad = examples.copy()
    bad.loc[0, "example_type"] = "slang"
    assert any("unknown example_type" in p for p in _problems(bad, topics))
    bad = examples.copy()
    bad.loc[0, "review_status"] = "approved"
    assert any("unknown review_status" in p for p in _problems(bad, topics))
    bad = examples.copy()
    bad.loc[0, "example_question"] = "  "
    assert any("empty values in example_question" in p for p in _problems(bad, topics))
    bad = examples.copy()
    bad.loc[0, "example_question"] = bad.loc[0, "example_question"] + " "
    assert any("whitespace in example_question" in p for p in _problems(bad, topics))
    bad = examples.copy()
    bad.loc[1, "example_question"] = bad.loc[0, "example_question"].upper()
    assert any("EX-0002: duplicate" in p for p in _problems(bad, topics))
    bad = examples.copy()
    bad.loc[0, "created_date"] = "15/10/2026"
    assert any("created_date" in p for p in _problems(bad, topics))


def test_example_validator_rejects_inaccurate_provenance(examples, topics):
    bad = examples.copy()
    bad.loc[0, "author"] = "owner"  # examples were not written by the owner
    assert any("EX-0001: author" in p for p in _problems(bad, topics))
    bad = examples.copy()
    bad.loc[0, "provenance"] = "owner-written"
    assert any("EX-0001: provenance" in p for p in _problems(bad, topics))
    bad = examples.copy()
    bad.loc[0, "provenance"] = "synthetic"
    assert any("EX-0001: provenance" in p for p in _problems(bad, topics))


@pytest.mark.parametrize("text, flag", [
    ("Chat Doctor, what is dehydration?", "chat_doctor_token_any"),
    ("Is 500 mg of vitamin D enough?", "dose_amount"),
    ("Contact me at someone@example.com about sleep?", "email_address"),
])
def test_example_validator_rejects_artefacts_dosing_and_privacy(examples, topics, text, flag):
    bad = examples.copy()
    bad.loc[0, "example_question"] = text
    problems = _problems(bad, topics)
    assert any(p.startswith("EX-0001") and flag in p for p in problems)
    assert not any(text in p for p in problems)  # messages never echo question text


def test_dataset_copy_detectors_return_ids_only():
    dataset = ["Hi thanks for the query the most likely cause is a viral infection of the throat today"]
    texts = {"EX-0001": "Is the most likely cause is a viral infection of the throat?",
             "EX-0002": "What is general information about sleep?"}
    found = curated.dataset_copy_ids(texts, dataset)
    assert found == ["EX-0001"]
    assert curated.dataset_copy_ids({"EX-0003": "Too short."}, dataset) == []
    keys = [curated.audit.normalize_question("What is general information about sleep?")]
    assert curated.dataset_question_matches(texts, keys) == ["EX-0002"]


@pytest.mark.skipif(not (config.PROCESSED_DIR / "querymate_clean.parquet").exists(),
                    reason="processed dataset not present")
def test_examples_share_no_text_with_dataset(examples):
    # Assertions compare ID lists only, so a failure never prints dataset text.
    d = pd.read_parquet(config.PROCESSED_DIR / "querymate_clean.parquet",
                        columns=["question", "answer", "question_norm_key", "display_allowed"])
    texts = dict(zip(examples["example_id"], examples["example_question"]))
    assert curated.dataset_question_matches(texts, d["question_norm_key"]) == []
    assert curated.dataset_copy_ids(texts, d["question"]) == []
    assert curated.dataset_copy_ids(texts, d["answer"]) == []
    assert not d["display_allowed"].any()


def _ex(*questions):
    return pd.DataFrame({"example_id": [f"EX-{i:04d}" for i in range(1, len(questions) + 1)],
                         "example_question": list(questions)})


def _ev(**questions):
    return pd.DataFrame({"question_id": list(questions), "question": list(questions.values())})


def test_eval_overlap_finds_exact_matches_after_normalisation():
    pairs = curated.eval_set_overlap(_ex("What is Vitamin D for?"),
                                     _ev(V001="what is vitamin d for", T001="How do vaccines work?"))
    assert [p[:3] for p in pairs] == [("exact", "EX-0001", "V001")]


def test_eval_overlap_finds_near_matches():
    pairs = curated.eval_set_overlap(
        _ex("What are the usual warning signs of dehydration?"),
        _ev(T001="What are the common warning signs of dehydration?", V001="How do vaccines work?"))
    assert [p[:3] for p in pairs] == [("near", "EX-0001", "T001")]
    _, _, _, cos, jac = pairs[0]
    assert cos >= curated.OVERLAP_CHAR_COSINE or jac >= curated.OVERLAP_WORD_JACCARD


def test_eval_overlap_ignores_unrelated_questions():
    pairs = curated.eval_set_overlap(_ex("Why does the body need sleep?"),
                                     _ev(V001="How is cholesterol measured in a blood test?",
                                         T001="Can you write me a poem about trains?"))
    assert pairs == []


def test_eval_overlap_reports_ids_and_scores_only():
    q = "What are the usual warning signs of dehydration?"
    pairs = curated.eval_set_overlap(_ex(q), _ev(T001=q))
    assert all(isinstance(v, (str, float)) for p in pairs for v in p)
    assert q not in repr(pairs) and q.lower() not in repr(pairs)


def test_leakage_loader_reads_both_sets_ids_and_questions_only():
    ev = curated.load_eval_questions_for_leakage_check()
    assert list(ev.columns) == ["question_id", "question"]
    assert len(ev) == 100 and ev["question_id"].is_unique
    assert ev["question_id"].str.fullmatch(r"[VT]\d{3}").all()


def test_examples_do_not_copy_evaluation_questions(examples):
    pairs = curated.eval_set_overlap(examples, curated.load_eval_questions_for_leakage_check())
    assert [p for p in pairs if p[0] == "exact"] == []
    # Near pairs are for manual review, not failures; check they are well-formed IDs only.
    assert all(e.startswith("EX-") and q[0] in "VT" for _, e, q, _, _ in pairs)


@pytest.mark.parametrize("text, flag", [
    ("What should I do if someone has chest pain?", "chest_pain"),
    ("When is it an emergency to call an ambulance?", "urgent_help_terms"),
    ("What if a friend says they want to die?", "crisis_terms"),
    ("What happens if someone took too many sleeping tablets?", "crisis_terms"),
    ("Why might a person suddenly collapse?", "collapse_terms"),
    ("What is the worst headache someone can get?", "sudden_severe_terms"),
    ("Can an overdose of vitamins happen?", "overdose_or_poisoning"),
])
def test_emergency_review_flags_flagged_examples(text, flag):
    flags = curated.emergency_review_flags(_ex(text))
    assert flags and flags[0][0] == "EX-0001" and flag in flags[0][1]
    assert text not in repr(flags)


@pytest.mark.parametrize("text", [
    "How does the body keep its fluid balance steady?",
    "What does a cholesterol blood test measure?",
    "Why do people get hay fever in spring?",
    "How does hand washing reduce the spread of colds?",
])
def test_emergency_review_flags_unflagged_examples(text):
    assert curated.emergency_review_flags(_ex(text)) == []


def test_emergency_review_flags_do_not_modify_examples(examples):
    before = examples.copy()
    flags = curated.emergency_review_flags(examples)
    pd.testing.assert_frame_equal(examples, before)
    assert all(e.startswith("EX-") for e, _ in flags)


# --- Validation topic labels -----------------------------------------------------

def test_labels_are_valid(labels, validation, topics):
    assert curated.validate_labels(labels, validation, set(topics["topic_id"])) == []


def test_labels_cover_all_40_validation_questions(labels, validation):
    assert len(labels) == 40
    assert list(labels["question_id"]) == list(validation["question_id"])
    assert set(labels["review_status"]) == {"owner_approved"}


def test_owner_review_decisions_recorded(labels):
    related = dict(zip(labels["question_id"], labels["related_topic_ids"]))
    assert related["V021"] == "TOP-110"
    assert related["V024"] == "TOP-002;TOP-201"
    assert related["V027"] == ""  # owner decision: no related topic without stronger justification


def test_policy_routed_questions_are_risk_indicators_only(labels, validation):
    merged = labels.merge(validation[["question_id", "category"]], on="question_id")
    policy = merged[merged["category"].isin(curated.POLICY_ROUTED_CATEGORIES)]
    assert len(policy) == 20
    assert set(policy["label_use"]) == {"risk_indicator_only"}
    assert set(policy["suggested_topic_id"]) == {"NONE"}


def test_label_validator_catches_problems(labels, validation, topics):
    ids = set(topics["topic_id"])
    bad = labels.copy()
    bad.loc[0, "suggested_topic_id"] = "TOP-999"
    assert any("unknown suggested_topic_id" in p for p in curated.validate_labels(bad, validation, ids))
    bad = labels.copy()
    bad.loc[20, "label_use"] = "graded"  # V021 is an emergency question
    assert any("risk_indicator_only" in p for p in curated.validate_labels(bad, validation, ids))
    bad = labels.copy()
    bad.loc[0, "related_topic_ids"] = "TOP-001;TOP-777"
    assert any("related_topic_ids" in p for p in curated.validate_labels(bad, validation, ids))
    bad = labels.copy()
    bad.loc[0, "rationale"] = validation.loc[0, "question"]
    assert any("copies a validation question" in p for p in curated.validate_labels(bad, validation, ids))
    assert curated.validate_labels(labels.iloc[:39], validation, ids)


def test_labels_file_contains_no_question_text(labels, validation):
    blob = labels.to_csv(index=False)
    assert not any(q in blob for q in validation["question"])


def test_curated_and_label_files_are_trackable():
    import subprocess
    for path in ["curated/topics.csv", "curated/topic_examples.csv",
                 "eval/validation_topic_labels.csv"]:
        r = subprocess.run(["git", "check-ignore", "-q", path], cwd=config.PROJECT_ROOT)
        assert r.returncode == 1, f"{path} is gitignored"
    r = subprocess.run(["git", "check-ignore", "-q", "data/processed/x.csv"], cwd=config.PROJECT_ROOT)
    assert r.returncode == 0  # other CSVs stay ignored
