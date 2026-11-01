"""Tests for the Topic Matcher and its validation-only evaluation (D-15).

Synthetic catalogues, except where marked. No test reads the Test set or dataset answers.
"""

import dataclasses
from pathlib import Path

import pandas as pd
import pytest

from querymate import curated, retrieval_eval, topic_eval, topic_matcher as tm
from querymate.topic_matcher import (AbstentionRule, GatedResult, PreCheckResult, Route, TopicMatch,
                                     TopicMatcher)

TOPICS = pd.DataFrame({
    "topic_id": ["TOP-001", "TOP-002", "TOP-003"],
    "topic_name": ["Hydration and dehydration", "Sleep basics for adults", "Hand hygiene"],
    "description": ["Why the body needs fluids and common signs of dehydration.",
                    "How much sleep adults need and sleep habits.",
                    "How hand washing reduces the spread of infections."],
})
EXAMPLES = pd.DataFrame({
    "example_id": ["EX-0001", "EX-0002", "EX-0003"],
    "topic_id": ["TOP-001", "TOP-002", "TOP-003"],
    "example_question": ["How can I tell if I am not drinking enough water?",
                         "How many hours of rest does a grown-up need each night?",
                         "Does scrubbing with soap stop germs spreading?"],
    "review_status": ["owner_approved", "pending_owner_review", "pending_owner_review"],
})
RULE = AbstentionRule(min_score=0.2)


def _matcher(method="word", rule=RULE, pending=False, examples=EXAMPLES):
    return TopicMatcher(method, rule).fit(TOPICS, examples, include_pending_examples=pending)


# --- Exact matches, paraphrases, ambiguity, no match ---------------------------------

@pytest.mark.parametrize("method", ["word", "char"])
def test_exact_topic_text_matches_with_score_one(method):
    m = _matcher(method).rank_for_evaluation("Sleep basics for adults")
    assert m.topic_id == "TOP-002" and m.score == pytest.approx(1.0, abs=1e-5)
    assert m.abstain_reason is None


def test_exact_owner_approved_example_matches():
    m = _matcher().rank_for_evaluation(EXAMPLES.loc[0, "example_question"])
    assert m.topic_id == "TOP-001" and m.score == pytest.approx(1.0, abs=1e-5)


@pytest.mark.parametrize("method", ["word", "char"])
@pytest.mark.parametrize("query, expected", [
    ("What are the signs of dehydration?", "TOP-001"),
    ("how much sleep do adults need", "TOP-002"),
    ("Does hand washing stop the spread of infections?", "TOP-003"),
])
def test_paraphrases_rank_the_right_topic_first(method, query, expected):
    assert _matcher(method).rank_for_evaluation(query).candidates[0].topic_id == expected


def test_ambiguous_query_abstains():
    m = _matcher().rank_for_evaluation("What does that mean?")
    assert m.topic_id == tm.NO_TOPIC
    assert m.abstain_reason in {"no_overlap", "below_min_score"}


def test_unrelated_query_has_no_overlap():
    m = _matcher().rank_for_evaluation("quantum chromodynamics lattice simulation")
    assert m.topic_id == tm.NO_TOPIC and m.abstain_reason == "no_overlap" and m.score == 0.0


def test_min_score_and_min_margin_abstention():
    q = "What are the signs of dehydration?"
    raw = _matcher(rule=AbstentionRule(0.0)).rank_for_evaluation(q)
    assert _matcher(rule=AbstentionRule(min_score=min(1.0, raw.score + 0.01))).rank_for_evaluation(q) \
        .abstain_reason == "below_min_score"
    assert _matcher(rule=AbstentionRule(0.0, min_margin=min(1.0, raw.margin + 0.01))).rank_for_evaluation(q) \
        .abstain_reason == "below_min_margin"


def test_ties_broken_by_topic_id_and_margin_zero():
    topics = pd.DataFrame({"topic_id": ["TOP-009", "TOP-004"], "topic_name": ["knee pain", "knee pain"],
                           "description": ["general knee pain", "general knee pain"]})
    m = TopicMatcher("word", AbstentionRule(0.1)).fit(topics).rank_for_evaluation("knee pain")
    assert [c.topic_id for c in m.candidates] == ["TOP-004", "TOP-009"] and m.margin == 0.0


def test_deterministic_across_fits_and_calls():
    a, b = _matcher(), _matcher()
    for q in ["dehydration signs", "sleep for adults", "hand washing"]:
        assert a.rank_for_evaluation(q) == b.rank_for_evaluation(q) == a.rank_for_evaluation(q)
    assert a.fingerprint() == b.fingerprint()


# --- Invalid inputs and configuration -------------------------------------------------

@pytest.mark.parametrize("bad", ["", "   ", "\n\t"])
def test_empty_query_rejected(bad):
    with pytest.raises(ValueError, match="enter a question"):
        _matcher().rank_for_evaluation(bad)


@pytest.mark.parametrize("bad", [None, 3, ["sleep"], b"sleep"])
def test_non_string_query_rejected(bad):
    with pytest.raises(TypeError):
        _matcher().rank_for_evaluation(bad)


def test_too_long_query_rejected():
    with pytest.raises(ValueError, match="too long"):
        _matcher().rank_for_evaluation("sleep " * 300)


@pytest.mark.parametrize("bad", [-0.1, 1.5, "0.3", True, None])
def test_invalid_rule_rejected(bad):
    with pytest.raises(ValueError):
        AbstentionRule(min_score=bad)
    with pytest.raises(ValueError):
        AbstentionRule(min_score=0.2, min_margin=bad)


def test_invalid_matcher_configuration():
    with pytest.raises(ValueError):
        TopicMatcher("bm25", RULE)
    with pytest.raises(TypeError):
        TopicMatcher("word", 0.3)
    with pytest.raises(RuntimeError):
        TopicMatcher("word", RULE).rank_for_evaluation("sleep")
    with pytest.raises(ValueError):
        TopicMatcher("word", RULE).fit(pd.concat([TOPICS, TOPICS.iloc[:1]]))
    bad = EXAMPLES.copy()
    bad.loc[0, "topic_id"] = "TOP-999"
    with pytest.raises(ValueError, match="unknown topics"):
        TopicMatcher("word", RULE).fit(TOPICS, bad)


# --- Pending examples are never treated as approved ----------------------------------

def test_pending_examples_excluded_by_default():
    m = _matcher()
    assert m.fingerprint()["examples_indexed"] == 1  # only the owner_approved one
    assert m.fingerprint()["example_statuses_indexed"] == ["owner_approved"]
    pending_q = EXAMPLES.loc[1, "example_question"]
    assert m.rank_for_evaluation(pending_q).score < 0.99
    assert not m.rank_for_evaluation(pending_q).uses_pending_examples


def test_pending_examples_only_with_explicit_flag_and_marked_provisional():
    m = _matcher(pending=True)
    assert m.fingerprint()["examples_indexed"] == 3
    r = m.rank_for_evaluation(EXAMPLES.loc[1, "example_question"])
    assert r.topic_id == "TOP-002" and r.score == pytest.approx(1.0, abs=1e-5)
    assert r.uses_pending_examples is True


def test_fit_does_not_modify_inputs():
    topics, examples = TOPICS.copy(), EXAMPLES.copy()
    _matcher(pending=True, examples=examples)
    pd.testing.assert_frame_equal(examples, EXAMPLES)
    pd.testing.assert_frame_equal(topics, TOPICS)


# --- Safety and scope precedence -------------------------------------------------------

POLICY_ROUTES = [r for r in Route if r is not Route.PROCEED]


@pytest.mark.parametrize("route", POLICY_ROUTES)
def test_policy_routes_pass_through_even_for_perfect_topic_match(route, monkeypatch):
    m = _matcher()
    perfect = "Sleep basics for adults"  # would score 1.0 if it were matched
    monkeypatch.setattr(m, "rank_for_evaluation", lambda *a, **k: pytest.fail("question was scored"))
    r = m.match_after_precheck(perfect, PreCheckResult(route, checked_by="stub"))
    assert r == GatedResult(route=route, match=None)
    assert r.topic_id == tm.NO_TOPIC


def test_proceed_route_matches():
    r = _matcher().match_after_precheck("how much sleep do adults need",
                                        PreCheckResult(Route.PROCEED, checked_by="stub"))
    assert r.route is Route.PROCEED and r.topic_id == "TOP-002"


@pytest.mark.parametrize("bad", [None, "proceed", Route.PROCEED, {"route": "proceed"},
                                 PreCheckResult("proceed", checked_by="stub")])
def test_matching_requires_a_real_precheck_result(bad):
    with pytest.raises(TypeError, match="PreCheckResult"):
        _matcher().match_after_precheck("sleep for adults", bad)


def test_routes_cover_every_policy_behaviour():
    behaviours = {"emergency_guidance", "crisis_guidance", "decline_diagnosis_refer",
                  "decline_dosage_refer", "out_of_scope_fallback", "safe_fallback", "invalid_input"}
    assert {r.value for r in POLICY_ROUTES} == behaviours


# --- No text in results; no dataset access -------------------------------------------------

def test_results_contain_ids_and_scores_only():
    assert {f.name for f in dataclasses.fields(TopicMatch)} == {
        "topic_id", "score", "margin", "candidates", "abstain_reason", "uses_pending_examples"}
    r = _matcher().rank_for_evaluation("signs of dehydration")
    assert "dehydration" not in repr(r).lower()


def test_matcher_module_does_not_read_dataset_or_external_services():
    code = Path(tm.__file__).read_text(encoding="utf-8").split('"""', 2)[2]  # skip module docstring
    for forbidden in ["read_parquet", "load_corpus", "PROCESSED", "import requests", "http", "anthropic",
                      "openai", "exclusions"]:  # exclusion text is never indexed
        assert forbidden not in code


# --- Real curated catalogue ------------------------------------------------------------------

def test_real_catalogue_default_uses_no_pending_examples():
    m = tm.build_from_curated("word", RULE)
    fp = m.fingerprint()
    assert fp["topics"] == 20 and fp["examples_indexed"] == 0 and not fp["uses_pending_examples"]
    assert set(curated.load_topic_examples()["review_status"]) == {"pending_owner_review"}


def test_real_catalogue_pending_flag_indexes_120_examples():
    fp = tm.build_from_curated("char", RULE, include_pending_examples=True).fingerprint()
    assert fp["examples_indexed"] == 120 and fp["uses_pending_examples"]


# --- Validation-only evaluation ----------------------------------------------------------------

def _results(rows):
    cols = ["question_id", "label_use", "expected_topic", "related_topics", "top1_topic", "top1_score", "margin"]
    return pd.DataFrame(rows, columns=cols)


def test_conservative_threshold_rejects_every_graded_none():
    res = _results([
        ("V1", "graded", "TOP-001", "", "TOP-001", 0.62, 0.3),
        ("V2", "graded", "TOP-002", "TOP-003", "TOP-003", 0.41, 0.1),
        ("V3", "graded", "NONE", "", "TOP-001", 0.35, 0.05),
        ("V4", "graded", "NONE", "", "TOP-002", 0.10, 0.02),
        ("V5", "risk_indicator_only", "NONE", "", "TOP-001", 0.50, 0.2),
    ])
    t = topic_eval.conservative_threshold(res)
    assert t == pytest.approx(0.3501)
    m = topic_eval.metrics_at(res, t)
    assert m["graded_none_accepted"] == []
    assert m["accepted_correct_strict"] == 1 and m["accepted_correct_lenient"] == 2
    assert m["accepted_wrong_topic"] == []
    assert m["policy_routed_would_match_without_gate"] == ["V5"]
    with pytest.raises(ValueError):
        topic_eval.conservative_threshold(res[res["expected_topic"] != "NONE"])


def test_evaluation_refuses_test_set(tmp_path):
    fake = tmp_path / "test_questions.csv"
    fake.write_text("question_id,question\nT001,x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="validation_questions.csv"):
        retrieval_eval.load_validation(fake)
    assert "test_questions" not in Path(topic_eval.__file__).read_text(encoding="utf-8")


def test_real_validation_evaluation_reports_ids_and_scores_only():
    questions, labels = topic_eval.load_inputs()
    res = topic_eval.evaluate(tm.build_from_curated("word", AbstentionRule(0.0)), questions, labels)
    assert len(res) == 40 and list(res["question_id"]) == list(questions["question_id"])
    blob = res.to_csv(index=False)
    assert not any(q in blob for q in questions["question"])
    assert res["question_id"].str.fullmatch(r"V\d{3}").all()
