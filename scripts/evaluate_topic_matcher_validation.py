"""Validation-only comparison of Topic Matcher configurations (D-15(c)).

Usage (from the project root):
    .venv\\Scripts\\python.exe scripts\\evaluate_topic_matcher_validation.py

Compares B1 (word TF-IDF) and B2 (character n-gram TF-IDF), each with topic names
and descriptions only and with the pending (not owner-approved) examples added.
Reads only eval/validation_questions.csv and the owner-approved validation topic
labels; never the Test set. Writes IDs and scores only to the gitignored reports/:
    topic_matcher_validation.json, topic_matcher_validation.md
Thresholds are provisional (n = 20 graded questions). Similarity is not evidence of
medical correctness, safety, or permission to display content (D-01, D-14, D-15(d)).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from querymate import audit, config, retrieval_eval, topic_eval  # noqa: E402
from querymate.topic_matcher import AbstentionRule, build_from_curated  # noqa: E402

CONFIGS = [("word", False), ("word", True), ("char", False), ("char", True)]
CAVEAT = ("Pending examples are AI-assisted, pending_owner_review, and may be influenced by the "
          "evaluation questions (D-15(b)); results using them are provisional and may be optimistic.")


def main() -> int:
    questions, labels = topic_eval.load_inputs()
    runs = []
    for method, pending in CONFIGS:
        matcher = build_from_curated(method, AbstentionRule(min_score=0.0), include_pending_examples=pending)
        results = topic_eval.evaluate(matcher, questions, labels)
        t = topic_eval.conservative_threshold(results)
        runs.append({
            "config": f"{method}{'+pending_examples' if pending else '+names_descriptions_only'}",
            "matcher": matcher.fingerprint(),
            "threshold_free": topic_eval.threshold_free(results),
            "conservative_threshold": t,
            "at_conservative_threshold": topic_eval.metrics_at(results, t),
            "paraphrase_consistency": topic_eval.paraphrase_consistency(results, questions),
            "per_question": results.to_dict(orient="records"),
        })

    report = {
        "metadata": {
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "evaluation_file": "eval/validation_questions.csv",
            "evaluation_file_sha256": audit.sha256_file(retrieval_eval.VALIDATION_FILE),
            "test_set_used": False,
            "threshold_rule": "lowest min_score rejecting every graded NONE question (pre-declared)",
            "caveats": [CAVEAT, "Graded NONE rejection is 100% by construction of the threshold rule.",
                        "n = 20 graded questions (10 topic, 10 NONE); all values provisional.",
                        "No safety/scope pre-check exists yet; policy-routed rows are risk indicators only."],
        },
        "runs": runs,
    }
    out = config.REPORTS_DIR
    out.mkdir(exist_ok=True)
    (out / "topic_matcher_validation.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    md = ["# Topic Matcher Validation Comparison", "",
          "> Validation set only; IDs and scores only. Provisional (n = 20 graded). "
          "Similarity is not evidence of medical correctness, safety, or permission to display.", "",
          *[f"- {c}" for c in report["metadata"]["caveats"]], "",
          "| config | top-1 strict | AUC | threshold | accepted correct (strict / lenient) | wrong topic | "
          "abstained on topic Qs | policy-routed matched without gate |",
          "|---|---|---|---|---|---|---|---|"]
    for r in runs:
        a, f = r["at_conservative_threshold"], r["threshold_free"]
        md.append(f"| {r['config']} | {f['top1_correct_strict']} | {f['auc_topic_vs_none_top1_score']} | "
                  f"{r['conservative_threshold']} | {a['accepted_correct_strict']}/{a['graded_topic_questions']} / "
                  f"{a['accepted_correct_lenient']}/{a['graded_topic_questions']} | {a['accepted_wrong_topic']} | "
                  f"{a['abstained_on_topic_questions']} | {a['policy_routed_would_match_without_gate']} |")
    (out / "topic_matcher_validation.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
