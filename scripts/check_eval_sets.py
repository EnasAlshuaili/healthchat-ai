"""Consistency, duplicate, and leakage checks for the draft evaluation sets.

Usage (from the project root):
    .venv\\Scripts\\python.exe scripts\\check_eval_sets.py

Checks schema and vocabularies, exact and near-duplicate questions within and
across eval/validation_questions.csv and eval/test_questions.csv, exact overlap
with dataset questions, and privacy patterns. Similarity is computed only among
the evaluation questions themselves; this is not retrieval.
"""

from __future__ import annotations

import re
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.metrics.pairwise import cosine_similarity  # noqa: E402

from querymate import audit, config  # noqa: E402

FILES = {"validation": config.EVAL_DIR / "validation_questions.csv",
         "test": config.EVAL_DIR / "test_questions.csv"}
PREFIX = {"validation": "V", "test": "T"}
COLUMNS = ["question_id", "question", "category", "expected_behavior", "rationale"]
CATEGORIES = {"general_education", "paraphrase", "ambiguous", "out_of_scope", "emergency",
              "diagnosis_request", "medication_dosage", "safe_fallback"}
BEHAVIORS = {"educational_answer_or_fallback", "clarify_or_fallback", "out_of_scope_fallback",
             "emergency_guidance", "crisis_guidance", "decline_diagnosis_refer",
             "decline_dosage_refer", "safe_fallback"}
EXPECTED_SIZE = {"validation": 40, "test": 60}
MIN_TEST_EMERGENCY = 15
MIN_TEST_CRISIS = 4
# Behaviours that are only valid for specific categories.
BEHAVIOR_CATEGORY = {"emergency_guidance": "emergency", "crisis_guidance": "emergency"}
CHAR_COSINE_THRESHOLD = 0.5
WORD_JACCARD_THRESHOLD = 0.5
STOPWORDS = {"a", "an", "the", "is", "are", "my", "i", "to", "of", "and", "for", "what", "it",
             "in", "do", "does", "can", "you", "me", "with", "how", "should", "if", "this", "that"}
PARAPHRASE_OF = re.compile(r"Paraphrase of ([VT]\d{3})")


def load() -> pd.DataFrame:
    frames = []
    for split, path in FILES.items():
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        df.insert(0, "split", split)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def words(text: str) -> set[str]:
    return {w for w in audit.normalize_question(text).split() if w not in STOPWORDS}


def main() -> int:
    df = load()
    problems: list[str] = []

    # Schema and vocabularies
    for split in FILES:
        part = df[df["split"] == split]
        if list(part.columns[1:]) != COLUMNS:
            problems.append(f"{split}: columns {list(part.columns[1:])}")
        if not part["question_id"].str.fullmatch(PREFIX[split] + r"\d{3}").all():
            problems.append(f"{split}: malformed question_id")
        for col in COLUMNS:
            if (part[col].str.strip() == "").any():
                problems.append(f"{split}: empty values in {col}")
    if df["question_id"].duplicated().any():
        problems.append("duplicate question_id values")
    if bad := set(df["category"]) - CATEGORIES:
        problems.append(f"unknown categories {bad}")
    if bad := set(df["expected_behavior"]) - BEHAVIORS:
        problems.append(f"unknown expected_behavior {bad}")

    # Size and coverage requirements
    for split, size in EXPECTED_SIZE.items():
        part = df[df["split"] == split]
        if len(part) != size:
            problems.append(f"{split}: {len(part)} rows, expected {size}")
        if missing := CATEGORIES - set(part["category"]):
            problems.append(f"{split}: missing categories {missing}")
    test = df[df["split"] == "test"]
    if (n_em := int((test["category"] == "emergency").sum())) < MIN_TEST_EMERGENCY:
        problems.append(f"test: {n_em} emergency rows, need >= {MIN_TEST_EMERGENCY}")
    if (n_cr := int((test["expected_behavior"] == "crisis_guidance").sum())) < MIN_TEST_CRISIS:
        problems.append(f"test: {n_cr} crisis_guidance rows, need >= {MIN_TEST_CRISIS}")
    for behavior, category in BEHAVIOR_CATEGORY.items():
        bad = df[(df["expected_behavior"] == behavior) & (df["category"] != category)]
        problems += [f"{q}: {behavior} outside category {category}" for q in bad["question_id"]]
    emergency_bad = df[(df["category"] == "emergency")
                       & ~df["expected_behavior"].isin(BEHAVIOR_CATEGORY)]
    problems += [f"{q}: emergency row without emergency/crisis behavior" for q in emergency_bad["question_id"]]

    # Paraphrase references must point to a general_education row in the same split
    ids = dict(zip(df["question_id"], df["split"]))
    cats = dict(zip(df["question_id"], df["category"]))
    declared = set()
    for qid, split, cat, rationale in zip(df["question_id"], df["split"], df["category"], df["rationale"]):
        m = PARAPHRASE_OF.search(rationale)
        if cat == "paraphrase" and not m:
            problems.append(f"{qid}: paraphrase row without 'Paraphrase of <ID>'")
        if m:
            src = m.group(1)
            declared.add(frozenset((qid, src)))
            if ids.get(src) != split:
                problems.append(f"{qid} paraphrases {src} from a different split or missing ID")
            elif cats[src] != "general_education":
                problems.append(f"{qid} paraphrases non-general row {src}")

    # Exact duplicates (normalised)
    df["norm"] = df["question"].map(audit.normalize_question)
    exact = df[df["norm"].duplicated(keep=False)]

    # Near duplicates: character n-gram TF-IDF cosine + content-word Jaccard
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), lowercase=True)
    sim = cosine_similarity(vec.fit_transform(df["question"]))
    wsets = [words(q) for q in df["question"]]
    pairs = []
    for i, j in combinations(range(len(df)), 2):
        union = wsets[i] | wsets[j]
        jac = len(wsets[i] & wsets[j]) / len(union) if union else 0.0
        if sim[i, j] >= CHAR_COSINE_THRESHOLD or jac >= WORD_JACCARD_THRESHOLD:
            a, b = df.iloc[i], df.iloc[j]
            kind = ("declared paraphrase" if frozenset((a.question_id, b.question_id)) in declared
                    else "CROSS-SPLIT" if a.split != b.split else "within split")
            pairs.append((kind, a.question_id, b.question_id, round(float(sim[i, j]), 2), round(jac, 2)))

    # Leakage: exact overlap with dataset questions
    overlap = None
    processed = config.PROCESSED_DIR / "querymate_clean.parquet"
    if processed.exists():
        keys = set(pd.read_parquet(processed, columns=["question_norm_key"])["question_norm_key"])
        overlap = df.loc[df["norm"].isin(keys), "question_id"].tolist()

    # Privacy patterns
    privacy = {name: int(sum(bool(rx.search(q.lower() if low else q)) for q in df["question"]))
               for name, (rx, low) in audit._COMPILED["privacy_indicators"].items()
               if name in {"email_address", "url", "phone_like_number", "self_identified_name",
                           "named_doctor_salutation", "date_like"}}

    # Report
    print("== Counts by split and category")
    print(pd.crosstab(df["category"], df["split"], margins=True).to_string())
    print("\n== Counts by split and expected behavior")
    print(pd.crosstab(df["expected_behavior"], df["split"], margins=True).to_string())
    print(f"\n== Exact duplicates (normalised): {len(exact)} rows")
    for _, r in exact.iterrows():
        print(f"  {r.question_id} ({r.split})")
    print(f"\n== Similar pairs (char cosine >= {CHAR_COSINE_THRESHOLD} or word Jaccard >= {WORD_JACCARD_THRESHOLD}): {len(pairs)}")
    for kind, a, b, c, j in sorted(pairs):
        print(f"  [{kind}] {a} ~ {b}  cosine={c} jaccard={j}")
    print(f"\n== Exact overlap with dataset questions: {overlap if overlap is not None else 'not checked (processed data missing)'}")
    print(f"\n== Privacy pattern matches: {privacy}")
    print("\n== Closest cross-split pairs regardless of threshold (for manual review)")
    val_idx = df.index[df["split"] == "validation"]
    test_idx = df.index[df["split"] == "test"]
    closest = sorted(((float(sim[i, j]), i, j) for i in val_idx for j in test_idx), reverse=True)[:8]
    for c, i, j in closest:
        print(f"  {df.at[i, 'question_id']} ~ {df.at[j, 'question_id']}  cosine={c:.2f}  "
              f"[{df.at[i, 'category']} / {df.at[j, 'category']}]")
    cross = [p for p in pairs if p[0] == "CROSS-SPLIT"]
    if exact.shape[0] or any(privacy.values()) or overlap:
        problems.append("exact duplicates, dataset overlap, or privacy matches found")
    print(f"\n== Problems: {problems or 'none'}")
    print(f"== Cross-split similar pairs needing manual review: {len(cross)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
