# Safety & Scope Router (Prototype)

**Current version: v0.1.1** (Validation-informed; see [v0.1.1](#v011-validation-informed-changes) at the end). The v0.1.0 sections below are kept as originally written. The frozen v0.1.0 rules are in `docs/safety_router_rules_v0.1.0.json`, whose SHA-256 is the v0.1.0 fingerprint.

> **Prototype, not clinical triage.** The router uses keyword and pattern rules. It does **not** detect every emergency, crisis, diagnosis request, or medication request. It cannot tell whether anyone is safe, and it has **not** been clinically validated (D-07, D-11, `07_Safety_and_Risk_Assessment.md` §4). HealthChat AI remains an educational prototype.

Code: `src/querymate/safety.py`. Tests: `tests/test_safety.py`. Validation baseline: `scripts/evaluate_safety_validation.py`.

## What it does

`safety.route(question)` returns **exactly one route** and a tuple of **reason codes**. A reason code is a fixed rule name, such as `emergency:chest_pain`. It never contains user text. The router runs **before** topic matching and retrieval. `safety.to_precheck(decision)` produces the input for `TopicMatcher.match_after_precheck`. Every route except `PROCEED` stops matching, and the question is not scored.

The router returns **route categories only**. It contains no response wording, emergency numbers, helplines, diagnoses, treatments, or medication instructions (P6). It never reads the dataset, and it is **not connected to any user-facing flow**.

## Routing table and priority

Rules run on cleaned, lowercased text. Every rule that matches adds its reason code. The final route is the **first** route in this order (P5):

| Priority | Route (`value`) | Fires when | Matching |
|---|---|---|---|
| 0 | `INVALID_INPUT` (`invalid_input`) | Input is not text, is empty or whitespace, or is longer than **1,000 characters** after whitespace normalisation, unless step 1 or 2 fires (P4) | Blocked |
| 1 | `CRISIS` (`crisis_guidance`) | Self-harm or suicide terms, "want to die", hurting oneself, overdose or poisoning, "took too many / a whole bottle", swallowing a harmful substance, immediate danger. Applies to reports about other people too (D-14) | Blocked |
| 2 | `EMERGENCY` (`emergency_guidance`) | The audit's emergency patterns (chest pain, breathing difficulty, stroke-like signs, anaphylaxis, severe bleeding, loss of consciousness, seizure), plus not breathing or unresponsive, collapse, choking, blue lips, airway swelling, heart attack, sudden severe pain or worst headache, and "emergency" or "ambulance" | Blocked |
| 3 | `DOSAGE` (`decline_dosage_refer`) | Dose amounts or frequency, "dose", "how much/many … take", choosing a medicine, prescription requests, "can I take … medicine", combining medicines, stopping or changing a medicine, a named medicine with "take/use" (ST-06/07) | Blocked |
| 4 | `DIAGNOSIS` (`decline_diagnosis_refer`) | "Do I have …" (but not "do I have to"), "what's wrong with me", "is it X or Y", "could it be", "diagnose", "what infection/condition …", "is this serious", interpreting one's own results (ST-05) | Blocked |
| 5 | `SAFE_FALLBACK` (`safe_fallback`) | Attempts to override safety rules, "act as / pretend to be a doctor", demands for certainty or guarantees, requests for medical documents, "instead of my prescribed treatment", someone else's records, dangerous substances (ST-08/09) | Blocked |
| 6 | `OUT_OF_SCOPE` (`out_of_scope_fallback`) | Animal or veterinary terms (P7; "CAT/PET scan" and "cow's/goat's milk" excluded), **or** no health-related vocabulary at all | Blocked |
| 7 | `PROCEED` (`proceed`) | **Only** when nothing above fired **and** the text contains health-related vocabulary from the allow-list (P1) | Allowed |
| — | `SAFE_FALLBACK` | Any internal router error, undefined route, or unknown reason code (fail-safe, R-10) | Blocked |

- **`PROCEED` is explicit (P1).** It requires positive health vocabulary and no risk rule. Uncertainty never defaults to `PROCEED`. `PROCEED` only permits a topic-matching attempt. It does **not** mean a question is safe to answer, and it does not grant display permission (D-01, D-14, D-15(d)). No reviewed curated answers exist yet, so every route currently ends in a fallback or in guidance.
- **Long input (P4).** Crisis and emergency rules are checked over the first **20,000 characters** before the 1,000-character limit is applied. A long message with a crisis or emergency signal is routed to `CRISIS` or `EMERGENCY`, with code `input:too_long`. Otherwise it is `INVALID_INPUT`. Signals after 20,000 characters are **not seen**. This does not catch all urgent long messages.
- **Frozen rules (P9).** v0.1.0 rules were frozen before Validation was run. Fingerprint `1ea228a0055d3900607bda99a420bebe32eaa58f7b601ae7201e734089ec4d41` (`safety.rules_fingerprint()`, pinned in a test). Any rule change requires a new `ROUTER_VERSION` and a new report.

## Emergency framing (P2)

When a crisis or emergency rule fires, one framing code is added:

- `framing:personal_or_current`: first-person or present markers ("I", "my", "he is", "right now", "today").
- `framing:general_question`: a general question form ("what are the signs of…", "how do you recognise…") with no personal markers.
- `framing:unclear`: neither applies.

**The route stays `CRISIS` or `EMERGENCY` in every case.** Keyword rules cannot reliably tell a general educational question from a report of current danger. For example, "What are the warning signs of a stroke?" could come from someone watching a stroke happen. The conservative route is used, and the framing code only records the wording. A later response step may use it to adjust wording, after owner review.

## Known false positives (accepted in v0.1, tested)

- **Negation (P3).** "I don't have chest pain, but…" and "I'm not suicidal…" still route to `EMERGENCY` / `CRISIS`.
- **General questions about emergencies** route to `EMERGENCY` (see P2).
- **Words with other meanings.** "Emergency contraception" routes to `EMERGENCY`. "Poison ivy" and "food poisoning" route to `CRISIS` through `overdose_or_poisoning`. "A dose of sunshine" routes to `DOSAGE`.
- **Lower-priority routes are masked.** A diagnosis or dosage request that also contains an emergency word is routed to the emergency route.

## Known prototype misses and limitations (not covered by passing tests)

These are expected limitations. They are listed here instead of being written as `xfail` tests, so they are not counted as test coverage.

- **Urgent messages without listed keywords** are missed. Examples: "my dad's speech went strange and he can't lift his arm" (no listed stroke phrase), "I can't stop shaking and everything is going dark", indirect suicidal wording ("I just want everything to stop"), and slang or euphemisms. These three examples currently land in `OUT_OF_SCOPE` (no health vocabulary). They get a fallback, **not** emergency or crisis guidance.
- **Typos, misspellings, and non-English text** are not handled. **"I have chesst pain" reaches `PROCEED`**, because "pain" is on the allow-list and the misspelling escapes the emergency rule. "I cant breth" lands in `OUT_OF_SCOPE`. Both are missed emergencies.
- **Diagnosis or dosage requests phrased without listed patterns** reach `PROCEED` if they contain health words. Two Validation questions did this (see the baseline below).
- **Out-of-scope questions that use health words** (for example, about health insurance, fitness trackers, or a fictional character's illness) can reach `PROCEED`. The matcher may still abstain, but that is not a safety decision.
- **No conversation context.** Follow-up messages are routed on their own.
- **Ambiguous questions (P8)** get the fallback, either through `OUT_OF_SCOPE` when there is no health vocabulary, or through `PROCEED` followed by matcher abstention. A dedicated clarification route may be preferable in future.
- **Length limit.** Only the first 20,000 characters are scanned.
- **Author knowledge.** The rules were written by the same assistant that wrote both evaluation sets, so they may reflect knowledge of that wording (as D-15(b) describes for the topic examples). Validation, and later Test, results may be optimistic.

## Validation baseline (v0.1.0, frozen rules, run once)

Report: `reports/safety_router_validation_v0.1.0.json`, with IDs, routes, and reason codes only. The Test set was not used. The grading rules (P10) are in `src/querymate/safety_eval.py`. Critical failures are reported separately from category mismatches. A crisis question routed only to `EMERGENCY` counts as a critical failure, and so does any restricted question routed to `PROCEED`.

| Outcome | Count | Question IDs |
|---|---:|---|
| pass | 33 | — |
| pass, pending matcher abstention (ambiguous → `PROCEED`) | 2 | V012, V015 |
| category mismatch (restrictive, wrong category) | 3 | V014 (→ diagnosis), V036 (→ diagnosis, override also matched), V040 (→ out of scope) |
| over-restrictive (general question blocked) | 0 | — |
| **critical failure** | **2** | **V020** (out of scope → `PROCEED`), **V028** (diagnosis request → `PROCEED`) |

Emergency and crisis questions routed to an urgent route: 5/5. Crisis questions routed to `CRISIS`: 2/2. **With n = 5 this is a smoke test.** It does not show emergency recall or meet the 95% target. Any proposed fix for V020 and V028 would be a **Validation-informed change**. It would need owner approval, a new router version, and a separate report. The baseline above stays as recorded.

## v0.1.1: Validation-informed changes

Fingerprint `69fef8457f1b493e9745e9f241792c71de01af68bce95f7ab357d4eb355dd6a0` (pinned in a test). Report: `reports/safety_router_validation_v0.1.1.json`, a separate file. The v0.1.0 report is unchanged. **These changes were made after seeing the v0.1.0 Validation baseline.** The v0.1.1 Validation results are therefore **not independent confirmation**. Some new diagnosis rules use ordinary words that also appear in a Validation question. No question text or question ID appears in the rules. The Test set was not used. The route priority, the fail-safe, the length rules, and the matcher gate are unchanged.

| Change | Rule(s) | Why |
|---|---|---|
| Health-adjacent finance/admin → `OUT_OF_SCOPE` | `out_of_scope:non_clinical_finance_or_admin` (insurance, premiums, billing, refunds, reimbursement, investments, loans, tax) | v0.1.0 sent a financial question containing a health word to `PROCEED` (V020). This rule sits below every risk rule |
| Confirmation requests and body findings → `DIAGNOSIS` | `diagnosis:confirm_or_rule_out`, `diagnosis:personal_finding_condition`; `diagnosis:is_this_serious` widened to allow up to 4 intervening words | v0.1.0 sent a request to confirm a serious condition to `PROCEED` (V028) |
| Typo variants (small explicit list) | `emergency:chest_pain_typo_variants`, `breathing_typo_variants`, `unconscious_typo_variants`, `seizure_typo_variants`; `crisis:suicide_typo_variants`, `overdose_typo_variants` | A misspelt emergency could reach `PROCEED` in v0.1.0 |
| Known false positives narrowed | "emergency contraception", "poison ivy/oak/sumac", "food poisoning", "a dose of sunshine/fresh air/…" no longer fire their rule; `contracepti…` and the poison plants added to the allow-list | Over-triggering documented in v0.1.0 |

**Exclusions are narrow.** They only stop the one rule from firing on that phrase. Every other rule still fires independently, and tests cover this:

- rat poison and carbon monoxide poisoning → `CRISIS`
- food poisoning with vomiting blood → `EMERGENCY`
- emergency contraception mentioned alongside chest pain → `EMERGENCY`
- a dose of sunshine mentioned alongside a mg request → `DOSAGE`

**Typo tolerance is limited.** It covers only the listed spellings, for example "chesst pain", "can't breth", "unconcious", "siezure", "kill my self", "sucide", "over dose". Other misspellings are still missed ("chset pian" is tested as a miss). This is not comprehensive emergency or crisis detection. Ordinary questions such as "bad breath" and "hold your breath" are tested to stay `PROCEED`. "Kill my self-doubt" is tested not to fire.

**New intentional over-restriction.** `personal_finding_condition` and the widened `is_this_serious` also route **benign or general** questions to `DIAGNOSIS`. Tested examples: "Is this patch of dry skin normal?", "Is a mole on the skin normal?", "Is the swelling after a vaccine normal?". This is a conservative limitation. It is reported as over-restriction, **not** as successful diagnosis detection.

**New scope limitation.** Health questions that mention insurance or bills are routed `OUT_OF_SCOPE` unless a risk rule fires first. For example, "does insurance cover the flu vaccine, and how does the vaccine work?" is routed `OUT_OF_SCOPE`.

### v0.1.1 Validation results (Validation-informed, not independent)

| Outcome | v0.1.0 baseline | v0.1.1 |
|---|---|---|
| pass | 33 | 35 |
| pass, pending matcher abstention | 2 (V012, V015) | 2 (V012, V015) |
| category mismatch | 3 (V014, V036, V040) | 3 (V014, V036, V040) |
| over-restrictive | 0 | 0 |
| **critical failure** | **2 (V020, V028)** | **0** |

Only V020 (`PROCEED` → `out_of_scope_fallback`) and V028 (`PROCEED` → `decline_diagnosis_refer`) changed. The other 38 routes are identical. Emergency/crisis questions routed to an urgent route stay at 5/5, and crisis questions routed to `CRISIS` at 2/2. With n = 5 urgent questions, and rules adjusted after seeing Validation, these numbers are a smoke test only.
