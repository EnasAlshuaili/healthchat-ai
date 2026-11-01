"""Validation-only analysis of TF-IDF ranking and candidate abstention signals.

Analysis only: no threshold is selected and nothing is routed or served.
Outputs contain question IDs, dataset source-row IDs, and scores only; no
dataset question or answer text (D-01, D-14).

Category-based groups are *proxies*. A category label does not prove that the
top-ranked dataset question is relevant; retrieval relevance requires manual review.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from querymate import config, retrieval

VALIDATION_FILE = config.EVAL_DIR / "validation_questions.csv"
TOP_K = 5

# Proxy groups (category-based; not relevance labels).
ANSWERABLE_PROXY = {"general_education", "paraphrase"}
ABSTAIN_PROXY = {"ambiguous", "out_of_scope"}
POLICY_ROUTED = {"emergency", "diagnosis_request", "medication_dosage", "safe_fallback"}

SIGNALS = ["top1_score", "margin", "relative_margin", "query_vocab_coverage"]
REVIEW_LABELS = ["relevant", "partially_relevant", "not_relevant", "cannot_judge"]
PARAPHRASE_OF = re.compile(r"Paraphrase of ([VT]\d{3})")


def load_validation(path: Path = VALIDATION_FILE) -> pd.DataFrame:
    """Load the validation set. Refuses any other file, so the test set cannot be used here."""
    path = Path(path)
    if path.name != "validation_questions.csv":
        raise ValueError("Retrieval analysis may only read eval/validation_questions.csv (D-09).")
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if not df["question_id"].str.fullmatch(r"V\d{3}").all():
        raise ValueError("Validation file contains non-validation question IDs.")
    return df


def proxy_group(category: str) -> str:
    if category in ANSWERABLE_PROXY:
        return "answerable_proxy"
    if category in ABSTAIN_PROXY:
        return "abstain_proxy"
    return "policy_routed"


def query_vocab_coverage(retriever: retrieval.TfidfRetriever, query: str) -> float:
    """Fraction of the query's unigram/bigram features that exist in the fitted vocabulary."""
    analyzer = retriever._vectorizer.build_analyzer()
    feats = analyzer(retrieval.prepare_query(retrieval.validate_query(query)))
    if not feats:
        return 0.0
    vocab = retriever._vectorizer.vocabulary_
    return round(sum(f in vocab for f in feats) / len(feats), 4)


def evaluate(retriever: retrieval.TfidfRetriever, questions: pd.DataFrame, top_k: int = TOP_K) -> pd.DataFrame:
    """One row per validation question: IDs, labels, and ranking signals only."""
    rows = []
    for q in questions.itertuples(index=False):
        res = retriever.search(q.question, top_k=top_k)
        top1 = res[0].score if res else 0.0
        top2 = res[1].score if len(res) > 1 else np.nan
        margin = top1 - top2 if len(res) > 1 else np.nan
        rows.append({
            "question_id": q.question_id,
            "category": q.category,
            "expected_behavior": q.expected_behavior,
            "proxy_group": proxy_group(q.category),
            "n_candidates": len(res),
            "top1_source_row": res[0].source_row if res else None,
            "top1_score": round(top1, 4),
            "top2_score": None if np.isnan(top2) else round(top2, 4),
            "margin": None if np.isnan(margin) else round(margin, 4),
            "relative_margin": None if np.isnan(margin) or top1 == 0 else round(margin / top1, 4),
            "query_vocab_coverage": query_vocab_coverage(retriever, q.question),
            "top_k_source_rows": ";".join(str(r.source_row) for r in res),
        })
    return pd.DataFrame(rows)


def category_summary(results: pd.DataFrame) -> pd.DataFrame:
    agg = {}
    for s in ["top1_score", "margin", "relative_margin", "query_vocab_coverage"]:
        agg[s] = results.groupby("category")[s].agg(["min", "median", "max"]).round(4)
    return pd.concat(agg, axis=1)


def signal_separation(results: pd.DataFrame, signal: str) -> dict:
    """Compare a signal between the answerable proxy and the abstain proxy.

    Returns AUC (probability an answerable-proxy question scores higher than an
    abstain-proxy one; 0.5 = no separation) and a threshold sweep showing how many
    of each group would be accepted at every observed value.
    """
    sub = results[results["proxy_group"].isin({"answerable_proxy", "abstain_proxy"})].dropna(subset=[signal])
    y = (sub["proxy_group"] == "answerable_proxy").astype(int).to_numpy()
    x = sub[signal].astype(float).to_numpy()
    auc = float(roc_auc_score(y, x)) if 0 < y.sum() < len(y) else None
    n_pos, n_neg = int(y.sum()), int(len(y) - y.sum())

    policy = results[results["proxy_group"] == "policy_routed"].dropna(subset=[signal])
    sweep = []
    for t in sorted(set(np.round(x, 4))):
        acc_pos = int(((x >= t) & (y == 1)).sum())
        acc_neg = int(((x >= t) & (y == 0)).sum())
        sweep.append({
            "accept_if_at_least": float(t),
            "answerable_proxy_accepted": f"{acc_pos}/{n_pos}",
            "abstain_proxy_accepted": f"{acc_neg}/{n_neg}",
            "policy_routed_accepted": f"{int((policy[signal].astype(float) >= t).sum())}/{len(policy)}",
        })
    return {"signal": signal, "auc_answerable_vs_abstain": None if auc is None else round(auc, 3),
            "n_answerable_proxy": n_pos, "n_abstain_proxy": n_neg, "sweep": sweep}


def overlap_cases(results: pd.DataFrame, signal: str = "top1_score") -> dict:
    """IDs of abstain-proxy or policy-routed questions scoring at or above the answerable-proxy minimum/median."""
    ans = results.loc[results["proxy_group"] == "answerable_proxy", signal].astype(float)
    lo, med = float(ans.min()), float(ans.median())
    others = results[results["proxy_group"] != "answerable_proxy"]
    return {
        "signal": signal,
        "answerable_proxy_min": round(lo, 4),
        "answerable_proxy_median": round(med, 4),
        "non_answerable_at_or_above_answerable_min": others.loc[others[signal] >= lo, "question_id"].tolist(),
        "non_answerable_at_or_above_answerable_median": others.loc[others[signal] >= med, "question_id"].tolist(),
    }


def paraphrase_consistency(results: pd.DataFrame, questions: pd.DataFrame) -> list[dict]:
    """For each declared paraphrase pair, overlap of retrieved source rows (no relevance claim)."""
    by_id = results.set_index("question_id")
    out = []
    for qid, rationale in zip(questions["question_id"], questions["rationale"]):
        m = PARAPHRASE_OF.search(rationale)
        if not m or m.group(1) not in by_id.index:
            continue
        a = set(filter(None, by_id.at[qid, "top_k_source_rows"].split(";")))
        b = set(filter(None, by_id.at[m.group(1), "top_k_source_rows"].split(";")))
        out.append({
            "paraphrase": qid, "source": m.group(1),
            "same_top1": bool(by_id.at[qid, "top1_source_row"] == by_id.at[m.group(1), "top1_source_row"]),
            "top_k_overlap": len(a & b),
        })
    return out


def hub_rows(results: pd.DataFrame) -> dict:
    """Source rows that appear as top-1 for more than one validation question."""
    counts = results["top1_source_row"].value_counts()
    repeated = counts[counts > 1]
    return {
        "distinct_top1_rows": int(results["top1_source_row"].nunique()),
        "questions": int(len(results)),
        "rows_top1_for_multiple_questions": {int(k): int(v) for k, v in repeated.items()},
    }


def review_sheet(results: pd.DataFrame) -> pd.DataFrame:
    """Manual-review sheet: IDs and scores only, with blank review fields."""
    sheet = results[["question_id", "category", "expected_behavior", "top1_source_row",
                     "top1_score", "top2_score", "margin", "top_k_source_rows"]].copy()
    sheet["retrieval_relevance"] = ""   # one of REVIEW_LABELS
    sheet["reviewer"] = ""
    sheet["review_date"] = ""
    sheet["notes"] = ""                 # do not paste dataset text or personal information
    return sheet
