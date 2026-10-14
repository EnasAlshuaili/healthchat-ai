# Business Requirements Document (BRD)
## QueryMate: AI Healthcare Question Answering Chatbot

- **Version:** 1.0
- **Status:** Draft for review
- **Domain:** Healthcare information / NLP / AI
- **Primary dataset:** `Doctor-HealthCare-100k.csv`

## 1. Executive summary
QueryMate is an AI-powered conversational prototype intended to answer general healthcare questions in understandable English. It will use a healthcare question-and-answer dataset and NLP-based retrieval, with a possible retrieval-augmented generation (RAG) approach if evaluation supports it. It must clearly communicate its limitations and direct users to professional care when appropriate.

## 2. Business problem
Users may encounter fragmented, confusing, or conflicting healthcare information online. A conversational interface can make general health information easier to access, but inaccurate or overconfident medical responses can cause harm. QueryMate therefore prioritizes understandable answers, uncertainty handling, privacy, and safety over answering every question.

## 3. Vision
Provide accessible, understandable, and safety-aware general healthcare information through a conversational AI assistant.

## 4. Objectives
- Accept healthcare questions written in natural language.
- Return relevant, readable answers using a documented AI/NLP approach.
- Inspect and prepare the selected dataset responsibly.
- Evaluate relevance, answer quality, latency, and safety.
- Handle uncertainty and potentially urgent symptom descriptions safely.
- Build a usable prototype with a clear medical disclaimer.

## 5. Stakeholders and users
- **Primary users:** people seeking general healthcare education.
- **Project team:** a single developer (solo educational portfolio project) responsible for data, NLP, interface, testing, and documentation.
- **Reviewer/supervisor:** none assigned; the developer self-reviews scope, methodology, results, and limitations.
- **Healthcare professional reviewer:** **not available.** No clinical review has occurred or is planned. All content and safety reviews are non-clinical self-reviews by the developer.

## 6. Scope
### In scope
- English text questions and answers.
- NLP preprocessing and dataset audit.
- Retrieval baseline, with semantic retrieval/RAG considered after baseline evaluation.
- Session-level conversational interface.
- General educational explanations.
- Visible disclaimer, safe fallback, and emergency-oriented guidance.
- Testing and evaluation documentation.

### Out of scope
- Definitive diagnosis or replacing a doctor.
- Prescribing medication or personalized dosage advice.
- Emergency triage as a clinically validated service.
- Access to electronic health records.
- Claims of clinical validation or regulatory approval.
- Persistent storage of sensitive health conversations unless separately designed and approved.

## 7. Business requirements
| ID | Requirement | Priority |
|---|---|---|
| BR-01 | Provide a conversational interface for general healthcare questions. | Must |
| BR-02 | Process questions in natural language. | Must |
| BR-03 | Return relevant responses grounded in the selected data/model approach. | Must |
| BR-04 | Clearly state the system is informational and not a doctor. | Must |
| BR-05 | Provide a safe response path for potentially urgent symptoms. | Must |
| BR-06 | Avoid unsupported certainty and provide fallback when uncertain. | Must |
| BR-07 | Audit dataset quality and verify usage/license conditions. | Must |
| BR-08 | Minimize collection and storage of personal health information. | Must |
| BR-09 | Evaluate response quality using a repeatable test set. | Must |
| BR-10 | Keep architecture modular enough to replace or improve the model. | Should |

## 8. Business rules
1. Safety takes priority over generating a complete answer.
2. The chatbot must not claim to be a licensed clinician.
3. Dataset answers are not automatically verified medical guidance.
4. The system must not promise a diagnosis or guaranteed correctness.
5. Potentially life-threatening symptoms should trigger concise emergency guidance.
6. Uncertain or unsupported questions should trigger clarification, a safe fallback, or professional referral.

## 9. Success measures
Proposed targets to validate after a baseline exists:
- At least 85% of sampled answers rated relevant by human evaluators.
- At least 80% of sampled answers rated understandable/helpful.
- Emergency test-set recall target of at least 95%, subject to test-set quality and review.
- Unsafe-response rate as close to zero as possible.
- Preferred response time of five seconds or less for the prototype under documented test conditions.

These are **targets, not achieved results**. The evaluation report must include actual scores, sample sizes, and limitations.

## 10. Risks
Main risks include incorrect medical content, hallucinations, dataset bias, outdated answers, failure to recognize urgent symptoms, privacy leakage, and over-reliance by users. See `07_Safety_and_Risk_Assessment.md`.

## 11. Assumptions and constraints
- Initial prototype is English-language.
- Development uses the available Doctor-HealthCare-100k dataset, subject to license review.
- Available compute may limit model size.
- This is an educational prototype and not approved for clinical use.
- This is a **solo educational portfolio project** built to learn NLP, Python, and Streamlit. It is experimental and not production-ready.
- **No clinician reviewer is available.** Development is not blocked by this; instead, the system must not claim clinical validation, medical accuracy, or production readiness, and any curated answer text is labelled as educational content that has not undergone clinical review (see `07_Safety_and_Risk_Assessment.md` §1.1).
- Human evaluation targets in §9 are measured by the developer alone; results must state this single-rater, non-clinical limitation.
- Dataset structure and quality must be confirmed by the data audit.

## 12. Deliverables
BRD, SRS, system design, dataset report, AI/NLP report, UI/UX design, safety assessment, testing plan, project plan, application prototype, and final report.
