"""Validation-only retrieval ranking and abstention-signal analysis.

Usage (from the project root):
    .venv\\Scripts\\python.exe scripts\\evaluate_retrieval_validation.py

Reads only eval/validation_questions.csv (never the test set). Writes, to the
gitignored reports/ directory:
    retrieval_validation_eval.json   per-question signals + summaries
    retrieval_validation_eval.md     human-readable summary
    retrieval_validation_review.csv  manual-review sheet (IDs and scores only)
No dataset question or answer text is written. No threshold is selected.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from querymate import audit, config, retrieval, retrieval_eval as rev  # noqa: E402


def _md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def main() -> int:
    questions = rev.load_validation()
    corpus = retrieval.load_corpus()
    retriever = retrieval.TfidfRetriever.from_corpus(corpus)
    results = rev.evaluate(retriever, questions)

    summary = rev.category_summary(results)
    separation = [rev.signal_separation(results, s) for s in rev.SIGNALS]
    overlap = rev.overlap_cases(results)
    paraphrases = rev.paraphrase_consistency(results, questions)
    hubs = rev.hub_rows(results)

    report = {
        "metadata": {
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "evaluation_file": "eval/validation_questions.csv",
            "evaluation_file_sha256": audit.sha256_file(rev.VALIDATION_FILE),
            "test_set_used": False,
            "retriever": retriever.fingerprint(),
            "top_k": rev.TOP_K,
            "note": "Category groups are proxies, not relevance labels. No threshold selected.",
        },
        "per_question": results.to_dict(orient="records"),
        "signal_separation": separation,
        "overlap_top1": overlap,
        "paraphrase_consistency": paraphrases,
        "hub_rows": hubs,
    }
    out = config.REPORTS_DIR
    out.mkdir(exist_ok=True)
    (out / "retrieval_validation_eval.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    rev.review_sheet(results).to_csv(out / "retrieval_validation_review.csv", index=False)

    md = ["# Retrieval Validation Analysis (TF-IDF baseline)", "",
          "> Validation set only. IDs and scores only; no dataset text. Category groups are proxies, "
          "not relevance labels. No threshold is selected. Similarity is not evidence of medical correctness "
          "or permission to display (D-01, D-14).", "",
          "## Per-category summary (min / median / max)", "",
          _md_table(summary.reset_index().set_axis(
              ["category"] + [f"{a} {b}" for a, b in summary.columns], axis=1)), "",
          "## Signal separation: answerable proxy (general_education + paraphrase) vs abstain proxy (ambiguous + out_of_scope)", ""]
    for s in separation:
        md += [f"### {s['signal']}: AUC = {s['auc_answerable_vs_abstain']} "
               f"(n = {s['n_answerable_proxy']} vs {s['n_abstain_proxy']})", "",
               _md_table(pd.DataFrame(s["sweep"])), ""]
    md += ["## Top-1 overlap cases", "", "```", json.dumps(overlap, indent=1), "```", "",
           "## Paraphrase consistency (retrieved source-row overlap, no relevance claim)", "",
           _md_table(pd.DataFrame(paraphrases)), "",
           "## Hub rows (top-1 for multiple questions)", "", "```", json.dumps(hubs, indent=1), "```", "",
           "## Per-question signals", "",
           _md_table(results.drop(columns=["top_k_source_rows"])), ""]
    (out / "retrieval_validation_eval.md").write_text("\n".join(md), encoding="utf-8")

    print(f"Fitted on {retriever.corpus_size:,} questions; evaluated {len(results)} validation questions.")
    for s in separation:
        print(f"  {s['signal']}: AUC answerable vs abstain proxy = {s['auc_answerable_vs_abstain']}")
    print("Wrote reports/retrieval_validation_eval.{json,md} and reports/retrieval_validation_review.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
