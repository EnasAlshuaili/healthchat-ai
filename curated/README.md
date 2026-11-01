# Curated Topic Catalogue (Provisional)

Decision **D-15** in `docs/DECISIONS.md`.

## What is here

| File | Status | Contents |
|---|---|---|
| `topics.csv` | Phase 1, provisional | 20 in-scope educational topics: ID, name, domain, neutral description, and exclusions |
| `topic_examples.csv` | Draft, **pending owner review** | 120 synthetic example questions (6 per topic), **AI-assisted (assistant-generated), not written by the owner**. See [Contamination limitation](#contamination-limitation). |
| `topic_content.json` | **One entry, owner reviewed** (D-21) | Educational content with its sources, evidence for each statement, and a review record. **Not clinically reviewed or clinically validated.** See [Curated answers](#curated-answers). |

## Rules

- **No medical answers.** Descriptions say what a topic covers, not what the answer is. They contain no advice, doses, diagnoses, or instructions.
- **No dataset text.** Nothing here is copied from `Doctor-HealthCare-100k.csv`. For `topics.csv`, tests check that no 8-word sequence is shared with any dataset question or answer, and that no dataset artefacts ("Chat Doctor"), dosing, prescribing, doctor-persona, or diagnostic-certainty wording appears. `topic_examples.csv` is checked by `curated.validate_topic_examples` and tests in `tests/test_curated.py` (schema, sequential IDs, exact topic names, 6 examples and 2 of each type per topic, assistant-generated provenance, review status, the same wording checks plus privacy patterns, and no exact or 8-word overlap with dataset questions or answers). Failures report example IDs only. Run `scripts/check_topic_examples.py` for an ID-only report; see [Automated checks for topic examples](#automated-checks-for-topic-examples).
- **Exclusions route elsewhere.** Each topic lists what it does not cover and which expected behavior applies instead (see `eval/README.md`). Emergencies always go to the emergency check first.
- **Topic matching is not a safety or display decision.** A topic match decides relevance only. It never overrides emergency/crisis handling, scope decisions, or display permission. Raw dataset answers are never displayed (`display_allowed = 0`, D-01).

## Curated answers

`topic_content.json` holds the only answer text HealthChat AI can display. It has one entry, `KN-0001` (hydration, `TOP-001`), knowledge version `0.1.0`. It was written from CDC and NHS pages and contains no dataset text.

- **Review.** `owner_reviewed` means the project owner reviewed the answer and its source mapping (2026-10-31). This is owner review of educational content only: **not** clinical review or medical validation. `clinical_review` must stay `not_clinically_reviewed`, or the file is rejected.
- **Display.** Only `owner_reviewed` entries can be displayed. A `pending_owner_review` entry loads but is never returned.
- **Evidence.** `statements` maps each factual statement in the answer to its source, section, and supporting wording. Each statement must appear in the answer, and each listed source must support at least one statement.
- **Source dates.** Each source records its dates and how it was checked. `review_overdue_when_checked` must be true when a printed next-review date has passed, so an overdue date cannot be dropped silently. The NHS water page is overdue (next review due 2026-05-17).
- **Matching.** `src/querymate/knowledge.py` matches a question only if it equals an entry in `approved_questions` after normalising case, punctuation, and spacing. This runs only after the Safety & Scope Router returns `PROCEED`. Anything else gets the safe fallback.
- **Changing the file.** Changing an answer, a source, or the question list needs a new owner review. Do not expand beyond this entry without an owner-approved decision.

## Deferred from this prototype

- Mental wellbeing and stress (risk of catching crisis messages that the crisis check missed).
- "When to seek medical care" (too close to emergency guidance).
- Pregnancy, children's health, cancer, and sexual health.

## Contamination limitation

The assistant that drafted this catalogue also wrote both evaluation sets, so the catalogue was drafted with knowledge of the topics those sets cover.

The planned safeguard was for the project owner to write all topic examples. **That safeguard was not applied** (D-15(b), amended 2026-10-15):

- The 120 examples in `topic_examples.csv` were generated with AI assistance. They were not written independently by the owner, and the file records this (`author = assistant`, `provenance = assistant-generated, synthetic`).
- The examples **may have been influenced by the evaluation questions.** The first draft contained one exact copy of a test question and several near-copies of validation and test questions.
- 33 examples were rewritten to reduce this overlap (their `provenance` says so). The validation and test sets were used **for leakage detection only**, not for tuning, threshold selection, or choosing examples that perform well.
- Lower similarity scores after rewriting do **not** show that the examples are independent of the evaluation sets. Some examples still ask a topic's core question (for example, how a cold differs from flu), and that question is also asked in the evaluation sets.
- All examples remain `pending_owner_review` until the owner has reviewed them.

Validation- and test-set results for topic matching may therefore be optimistic and **must be reported with this contamination caveat.**

## Automated checks for topic examples

```bash
.venv\Scripts\python.exe scripts\check_topic_examples.py
```

The script prints example IDs, evaluation question IDs, and scores only. It never prints question, example, or dataset text.

**Evaluation-set overlap (leakage detection).** `curated.eval_set_overlap` compares every example with every question in `eval/validation_questions.csv` and `eval/test_questions.csv`:

- **Exact:** identical text after normalisation (lowercase, punctuation removed). Any exact copy fails the check.
- **Near:** character 3–5-gram TF-IDF cosine **≥ 0.5** or content-word Jaccard **≥ 0.5**. These are the same uncalibrated thresholds as `scripts/check_eval_sets.py`, fixed before the results were seen. Near pairs are listed for manual review and do not fail the check.
- **Test-set use:** the Test set is read **for leakage detection only**, through a loader that keeps only `question_id` and `question`. It is not used to tune the matcher, choose thresholds, select topics, or rewrite examples. Flagged pairs are not fixed automatically. Any rewrite is an owner decision and must be recorded with this caveat.
- **Limitations:** both measures are lexical. They miss questions that mean the same thing in different words, and the thresholds are not calibrated. **Passing does not show that the examples are independent of the evaluation sets.** Conceptual overlap and the contamination described above remain.

**Topic Matcher (first version, `src/querymate/topic_matcher.py`).**

- **Method.** TF-IDF cosine similarity (word 1–2-grams, or character 3–5-grams) over each topic's name, description, and eligible examples. A topic's score is its best-matching text, and ties are broken by topic ID. Exclusion text is not indexed. The matcher returns topic IDs and scores, or `NONE` when the configured `AbstentionRule` (`min_score`, optional `min_margin`) is not met. There is no default threshold.
- **Safety first.** `match_after_precheck` scores a question only when a `PreCheckResult` says `PROCEED`. Every other route (emergency, crisis, diagnosis, dosage, out of scope, safe fallback) is returned unchanged with topic `NONE`, and the question is not scored. **No pre-check exists yet**: the safety/scope router is a separate, later step. `rank_for_evaluation` is ungated and for offline evaluation only.
- **Pending examples.** By default only `owner_approved` examples are indexed. Today that is none, so the matcher uses names and descriptions only. `include_pending_examples=True` is an experiment-only switch. Results produced with it are provisional and carry the contamination caveat above. No example's status is changed.
- **Evaluation.** `scripts/evaluate_topic_matcher_validation.py` compares configurations on the Validation set only, using the owner-approved labels, and writes IDs and scores to `reports/`. The threshold rule was fixed before results were seen: the lowest `min_score` at which no graded `NONE` question is accepted. Graded `NONE` rejection is therefore 100% by construction. With 20 graded questions every value is provisional.
- **What a match is not.** A match shows topical similarity only. It is not evidence of medical correctness or safety, and it does not grant permission to display content (D-01, D-14, D-15(d)).

**Emergency/crisis wording review flag.** `curated.emergency_review_flags` is a small keyword heuristic. It reuses the audit's emergency keyword patterns and adds a few urgency, crisis, collapse, and "sudden severe" phrases. It marks examples whose wording might resemble an emergency or crisis message so the owner can check them, because such examples could pull urgent messages towards an educational topic. It is **not** safety detection, triage, or clinical validation, and an unflagged example is not shown to be safe. Flagged examples are never rewritten automatically. Emergency and crisis handling stays with the separate safety check (D-07, D-14).
