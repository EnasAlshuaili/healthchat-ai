"""Validation-only evaluation of the Topic Matcher (D-15(c)).

Reads eval/validation_questions.csv (through retrieval_eval.load_validation, which
refuses any other file) and the owner-approved eval/validation_topic_labels.csv.
The Test set is never read here. Outputs contain IDs and scores only.

Threshold rule (owner decision 2026-10-19, fixed before any results were seen):
the lowest min_score at which no graded NONE question is accepted, i.e. just above
the highest top-1 score among graded NONE questions. Graded NONE questions are
therefore all rejected *by construction*; that is not evidence of abstention
quality. With 20 graded questions every threshold and metric is provisional.

Policy-routed questions are reported only as risk indicators: how many would
have matched a topic if the safety/scope gate were missing.
"""

from __future__ import annotations

import pandas as pd
from sklearn.metrics import roc_auc_score

from querymate import curated, retrieval_eval
from querymate.topic_matcher import NO_TOPIC, TopicMatcher

THRESHOLD_STEP = 1e-4  # "just above" the highest graded-NONE score


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validation questions and owner-approved topic labels (refuses unapproved labels)."""
    questions = retrieval_eval.load_validation()
    labels = curated.load_validation_labels()
    problems = curated.validate_labels(labels, questions, set(curated.load_topics()["topic_id"]))
    if problems:
        raise ValueError(f"validation topic labels failed validation: {problems}")
    if set(labels["review_status"]) != {"owner_approved"}:
        raise ValueError("All validation topic labels must be owner_approved before any run (D-15(c)).")
    return questions, labels


def evaluate(matcher: TopicMatcher, questions: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """One row per validation question with raw (ungated) scores. IDs and scores only."""
    lab = labels.set_index("question_id")
    rows = []
    for q in questions.itertuples(index=False):
        m = matcher.rank_for_evaluation(q.question)
        related = lab.at[q.question_id, "related_topic_ids"]
        rows.append({
            "question_id": q.question_id,
            "category": q.category,
            "label_use": lab.at[q.question_id, "label_use"],
            "expected_topic": lab.at[q.question_id, "suggested_topic_id"],
            "related_topics": related,
            "top1_topic": m.candidates[0].topic_id,
            "top1_score": m.score,
            "margin": m.margin,
            "top3": ";".join(f"{c.topic_id}:{c.score:.4f}" for c in m.candidates),
        })
    return pd.DataFrame(rows)


def conservative_threshold(results: pd.DataFrame) -> float:
    """Lowest min_score at which no graded NONE question is accepted (pre-declared rule)."""
    none_scores = results.loc[(results["label_use"] == "graded") & (results["expected_topic"] == NO_TOPIC),
                              "top1_score"]
    if none_scores.empty:
        raise ValueError("No graded NONE questions to derive a threshold from.")
    return round(min(1.0, float(none_scores.max()) + THRESHOLD_STEP), 6)


def _accepted(results: pd.DataFrame, min_score: float, min_margin: float) -> pd.Series:
    return (results["top1_score"] > 0) & (results["top1_score"] >= min_score) & (results["margin"] >= min_margin)


def metrics_at(results: pd.DataFrame, min_score: float, min_margin: float = 0.0) -> dict:
    """Counts and question IDs at a given rule. Strict = suggested topic; lenient also allows related topics."""
    acc = _accepted(results, min_score, min_margin)
    graded = results["label_use"] == "graded"
    has_topic = graded & (results["expected_topic"] != NO_TOPIC)
    none_rows = graded & (results["expected_topic"] == NO_TOPIC)
    policy = results["label_use"] == "risk_indicator_only"
    strict = results["top1_topic"] == results["expected_topic"]
    lenient = strict | results.apply(
        lambda r: r["top1_topic"] in set(filter(None, r["related_topics"].split(";"))), axis=1)
    ids = lambda mask: results.loc[mask, "question_id"].tolist()  # noqa: E731
    return {
        "min_score": min_score, "min_margin": min_margin,
        "graded_topic_questions": int(has_topic.sum()),
        "accepted_correct_strict": int((has_topic & acc & strict).sum()),
        "accepted_correct_lenient": int((has_topic & acc & lenient).sum()),
        "accepted_wrong_topic": ids(has_topic & acc & ~lenient),
        "abstained_on_topic_questions": ids(has_topic & ~acc),
        "graded_none_questions": int(none_rows.sum()),
        "graded_none_accepted": ids(none_rows & acc),
        "policy_routed_questions": int(policy.sum()),
        "policy_routed_would_match_without_gate": ids(policy & acc),
    }


def threshold_free(results: pd.DataFrame) -> dict:
    """Top-1 topic accuracy on graded topic questions, and score separation topic vs NONE."""
    graded = results[results["label_use"] == "graded"]
    topic = graded[graded["expected_topic"] != NO_TOPIC]
    y = (graded["expected_topic"] != NO_TOPIC).astype(int)
    auc = float(roc_auc_score(y, graded["top1_score"])) if 0 < y.sum() < len(y) else None
    return {
        "top1_correct_strict": f"{int((topic['top1_topic'] == topic['expected_topic']).sum())}/{len(topic)}",
        "auc_topic_vs_none_top1_score": None if auc is None else round(auc, 3),
        "graded_topic_score_min_median": [round(float(topic["top1_score"].min()), 4),
                                          round(float(topic["top1_score"].median()), 4)],
        "graded_none_score_max": round(float(graded.loc[graded["expected_topic"] == NO_TOPIC,
                                                         "top1_score"].max()), 4),
    }


def paraphrase_consistency(results: pd.DataFrame, questions: pd.DataFrame) -> list[dict]:
    """Whether each declared paraphrase pair gets the same top-1 topic."""
    top1 = dict(zip(results["question_id"], results["top1_topic"]))
    out = []
    for qid, rationale in zip(questions["question_id"], questions["rationale"]):
        if m := retrieval_eval.PARAPHRASE_OF.search(rationale):
            out.append({"paraphrase": qid, "source": m.group(1),
                        "same_top1_topic": top1.get(qid) == top1.get(m.group(1))})
    return out
