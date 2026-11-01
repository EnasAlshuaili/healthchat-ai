"""Checks for curated/topic_examples.csv (D-15). Reports IDs and scores only.

Usage (from the project root):
    .venv\\Scripts\\python.exe scripts\\check_topic_examples.py

Runs the schema/provenance validator, dataset-copy checks, exact and near-duplicate
overlap with both evaluation sets, and the emergency/crisis wording review flag.
The Test set is read for leakage detection only; it is never used to tune, select,
or rewrite anything. No question, example, or dataset text is printed.

Exit code 1 for validation problems, dataset copies, or exact evaluation-set copies.
Near-duplicate pairs and emergency/crisis flags are for manual review and do not fail.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from querymate import config, curated  # noqa: E402


def main() -> int:
    topics = curated.load_topics()
    examples = curated.load_topic_examples()
    problems = curated.validate_topic_examples(examples, topics)

    print(f"== Examples: {len(examples)}; review_status: "
          f"{examples['review_status'].value_counts().to_dict()}")
    print(f"== Validator problems: {problems or 'none'}")

    processed = config.PROCESSED_DIR / "querymate_clean.parquet"
    if processed.exists():
        d = pd.read_parquet(processed, columns=["question", "answer", "question_norm_key"])
        texts = dict(zip(examples["example_id"], examples["example_question"]))
        copies = {"exact dataset question": curated.dataset_question_matches(texts, d["question_norm_key"]),
                  f"{curated.SHINGLE_WORDS}-word overlap with dataset questions":
                      curated.dataset_copy_ids(texts, d["question"]),
                  f"{curated.SHINGLE_WORDS}-word overlap with dataset answers":
                      curated.dataset_copy_ids(texts, d["answer"])}
        for name, ids in copies.items():
            print(f"== {name}: {ids or 'none'}")
            if ids:
                problems.append(name)
    else:
        print("== Dataset-copy checks: not run (processed data missing)")

    pairs = curated.eval_set_overlap(examples, curated.load_eval_questions_for_leakage_check())
    exact = [p for p in pairs if p[0] == "exact"]
    near = [p for p in pairs if p[0] == "near"]
    print(f"\n== Exact evaluation-set copies: {len(exact)}")
    for _, e, q, c, j in exact:
        print(f"  {e} = {q}")
    print(f"== Near-duplicate pairs (char cosine >= {curated.OVERLAP_CHAR_COSINE} or "
          f"word Jaccard >= {curated.OVERLAP_WORD_JACCARD}), for manual review: {len(near)}")
    for _, e, q, c, j in near:
        print(f"  {e} ~ {q}  cosine={c} jaccard={j}")
    if exact:
        problems.append("exact evaluation-set copies")

    flags = curated.emergency_review_flags(examples)
    print(f"\n== Emergency/crisis wording review flags (heuristic, not safety detection): {len(flags)}")
    for e, hits in flags:
        print(f"  {e}: {hits}")

    print("\nPassing these checks does not show the examples are independent of the "
          "evaluation sets; conceptual overlap and contamination may remain (D-15).")
    print(f"== Problems: {problems or 'none'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
