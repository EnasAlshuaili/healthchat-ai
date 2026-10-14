# Decision Log
## QueryMate: AI Healthcare Question Answering Chatbot

Decisions approved by the project owner. Record new decisions and changes here (see `09_Project_Plan.md` §7).

| ID | Date | Decision | Rationale / notes |
|---|---|---|---|
| D-01 | 2026-10-13 | **Do not display raw dataset answers.** Use the dataset for retrieval experiments only. Display only answer content that has passed a documented review and safety process. Regex sanitization alone is not sufficient. | Dataset answers contain prescriptions, dosages, diagnostic certainty, a doctor persona, and corrupted text (see Phase 1 audit). |
| D-02 | 2026-10-13 | When no reviewed, relevant answer exists, show a safe fallback explaining the limitation and recommending a qualified healthcare professional where appropriate. | BR-06, FR-07. |
| D-03 | 2026-10-13 | Stack: Streamlit + plain Python. No FastAPI in the MVP. | Simplicity (NFR-06, 03_System_Design §7). |
| D-04 | 2026-10-13 | Use a dedicated Python 3.12 virtual environment (`.venv`). Do not modify the system Python. | Reproducibility; wider library support than 3.14. |
| D-05 | 2026-10-13 | Retrieval baseline: TF-IDF + cosine similarity. Consider sentence embeddings only after the baseline is evaluated. | 05_AI_NLP_Model_Report §3, §9. |
| D-06 | 2026-10-13 | LLM APIs, RAG, and fine-tuning are out of scope for the MVP. No health questions or dataset content are sent to external AI services. | Privacy, hallucination risk, cost. |
| D-07 | 2026-10-13 | Emergency guidance uses generic wording ("contact local emergency services immediately") until location-specific contacts are verified. Emergency detection is described as a prototype safeguard, not clinically reliable triage. | 07_Safety_and_Risk_Assessment §4. |
| D-08 | 2026-10-13 | Dataset license/provenance remains **unverified**. No redistribution or public deployment until permitted use is established. Original CSV kept unchanged (SHA-256 recorded in `src/querymate/config.py`); cleaning happens on a separate copy with a cleaning log. | BR-07, 04_Dataset_Analysis §9. |
| D-09 | 2026-10-13 | Separate validation and test sets are created **before** threshold tuning, covering relevant, paraphrased, unrelated, ambiguous, and safety-focused questions. No claims of clinical validation. | 08_Testing_Plan §5, 04_Dataset_Analysis §7. |
| D-10 | 2026-10-13 | Repository layout: docs in `docs/`, dataset in `data/raw/`, original ZIP archive left unchanged in the root (gitignored). Raw data, secrets, and sensitive data are never committed. | Approved file organization. |

| D-11 | 2026-10-13 | Solo educational portfolio project; **no clinician reviewer is available**, and development is not blocked by this. Curated answers are written/reviewed by the developer and labelled as educational content that has not undergone clinical review. No claims of clinical validation, medical accuracy, or production readiness. Work proceeds in small steps with owner review between steps. | Resolves the D-01 reviewer question. See 01_BRD §5, §11 and 07_Safety §1.1. |
| D-12 | 2026-10-13 | Dataset audit (step 2) uses Python `re` for all pattern matching (not the pandas/Arrow RE2 engine) and reports aggregated counts only; no dataset text or matched personal data is written to reports. | Consistent regex semantics; privacy (BR-08). |

| D-13 | 2026-10-14 | Cleaning (step 3) applies only technical transformations: escape decoding, typographic and whitespace normalisation, NFC, and email/URL redaction. No rows are deleted; unusable or duplicate questions are marked as not retrieval-eligible (E1/E2). Every row keeps `source_row` and hashes of its original text. "Chat Doctor" placeholders, medical wording, truncation, and conflicting answers are flagged, never rewritten or merged. `display_allowed` is False for all rows. | FR-03, D-01, D-08; owner's step 3 requirements. |

| D-14 | 2026-10-14 | Evaluation conventions (see `eval/README.md`): (a) `crisis_guidance` is a distinct expected behavior used when self-harm risk, a possible overdose, or immediate danger is present or cannot safely be excluded; it must include the immediate emergency direction plus generic crisis support, without first asking about intent. (b) Responses are graded on required elements: an `emergency_guidance` case still passes if it adds crisis wording; a `crisis_guidance` case fails without crisis support. (c) `safe_fallback` is a general fallback and never substitutes for required emergency or crisis guidance. (d) Similarity scores alone never determine pass/fail or permission to display. | Safety §4 ("immediate crisis/emergency guidance"; no long questioning first), D-01, D-07; owner decision on V024. Evaluation convention, not clinical policy; requires future review. |

## Open items
- Review-record format for curated answers (fields such as topic, text, sources consulted, reviewer, date, "not clinically reviewed" label). To be defined before step 5/6.
- Dataset Kaggle URL, author, license and download date (D-08).
- Deadline.
- Evaluation policy choices not settled by existing documentation (D-14): wording of generic crisis support; whether "prompt" professional evaluation is required for potentially serious conditions; whether non-human (veterinary) health questions are explicitly out of scope; detailed per-item grading procedure and reviewer. See `eval/README.md` "Unresolved policy choices".
