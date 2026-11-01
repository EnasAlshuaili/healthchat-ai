# System Design Document (SDD)
## HealthChat AI: Educational Healthcare Q&A Chatbot

- **Version:** 1.0
- **Status:** Proposed architecture; confirm during implementation

## 1. Design goals
- Keep the first version simple and reproducible.
- Separate the interface, retrieval, safety checks, and data preparation.
- Prefer grounded retrieval before adding free-form generation.
- Avoid collecting sensitive user data unnecessarily.
- Make model and safety evaluation possible independently.

## 2. Proposed high-level architecture

```text
User
 |
 v
Streamlit Chat UI (proposed)
 |
 v
Input validation / text normalization
 |
 v
Safety pre-check ---------------------> Emergency guidance when high risk
 |
 v
Question encoder / retrieval
 |
 v
Top-k dataset Q&A candidates
 |
 v
Confidence threshold
 |                         |
 | confident               | low confidence
 v                         v
Retrieved answer/context   Safe fallback / clarification
 |                         |
 +------------+------------+
              |
              v
Post-response safety checks
              |
              v
Disclaimer + final response
              |
              v
User
```

This is a proposal, not a claim that these components have already been implemented.

## 3. Component responsibilities
### 3.1 User interface
Collects the question, shows the disclaimer, renders the response, displays errors, and supports clearing the current session.

### 3.2 Input validation
Rejects blank or excessively long inputs, normalizes whitespace, and avoids transformations that could alter meaning.

### 3.3 Safety pre-check
Checks a conservative, documented set of emergency indicators and routes high-risk messages to a safety response. Keyword rules alone are not a clinically reliable emergency detector; they must be tested and described as a prototype safeguard.

### 3.4 Retrieval service
Indexes approved question/answer text and returns top-k candidates with similarity scores. Begin with TF-IDF/cosine similarity as a baseline; compare with sentence embeddings if resources permit.

### 3.5 Answer policy
Use a validated similarity threshold. If no candidate is sufficiently relevant, do not return a random nearest answer. Use a fallback. If an LLM is added, provide retrieved context and require it to avoid unsupported claims.

### 3.6 Response safety validation
Checks for unsafe certainty, diagnosis claims, or disallowed medication instructions where feasible. Automated checks do not replace clinical review.

### 3.7 Logging and metrics
Record non-sensitive operational metrics such as latency, error type, retrieval score, and aggregate counts. Do not log complete health conversations by default.

## 4. Data flow
1. User submits a question.
2. UI validates input.
3. Safety pre-check runs.
4. If high risk, show emergency/professional guidance.
5. Otherwise normalize the question and retrieve candidates.
6. Compare the best score against a validated threshold.
7. Return a grounded response or safe fallback.
8. Run response safety checks.
9. Render the answer and disclaimer.
10. Store the conversation in session memory only unless a documented storage feature is added.

## 5. Dataset schema
The uploaded file is expected to contain columns named `instruction`, `input`, and `output`. Confirm the actual schema in `04_Dataset_Analysis.md` before coding. Recommended conceptual mapping:
- Question text: `input`
- Reference answer: `output`
- Instruction: review whether useful for retrieval/training; do not blindly concatenate it into every user question.

## 6. Suggested project structure

```text
querymate/
├── app.py
├── requirements.txt
├── .env.example
├── README.md
├── data/
│   ├── raw/              # keep source dataset unchanged
│   ├── processed/        # generated cleaned data; usually gitignored
│   └── index/             # generated retrieval index; usually gitignored
├── src/
│   ├── config.py
│   ├── preprocessing.py
│   ├── dataset_audit.py
│   ├── retrieval.py
│   ├── safety.py
│   ├── response_policy.py
│   └── evaluation.py
├── tests/
│   ├── test_preprocessing.py
│   ├── test_retrieval.py
│   └── test_safety.py
└── docs/
    └── project documentation files
```

## 7. Technology proposal
- Language: Python.
- Data processing: pandas, NumPy.
- Baseline retrieval: scikit-learn TF-IDF and cosine similarity.
- Optional semantic retrieval: Sentence Transformers and FAISS/Chroma, selected after benchmarking.
- Initial UI: Streamlit for rapid prototyping.
- Optional API layer: FastAPI only if frontend/backend separation becomes useful.
- Testing: pytest plus manually reviewed test prompts.

Do not add an LLM API dependency until cost, privacy, latency, and output-safety implications are reviewed.

## 8. Configuration and secrets
- Keep secrets in environment variables.
- Include `.env.example` with placeholder values only.
- Add `.env`, raw datasets, model weights, and private logs to `.gitignore` where licensing/privacy require.
- Pin dependency versions after confirming a working environment.

## 9. Failure modes
- Missing dataset/index: display a setup error and stop answering.
- No relevant retrieval result: safe fallback.
- Model unavailable: graceful service error.
- Safety module error: fail safely for the affected request rather than bypassing safety.
- Invalid input: explain how to correct it.

## 10. Architecture decisions to record
- Selected retrieval approach and reason.
- Threshold calibration method.
- Whether generative AI is used.
- Dataset license/usage decision.
- Hosting and privacy settings.
