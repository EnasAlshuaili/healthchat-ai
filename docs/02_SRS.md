# Software Requirements Specification (SRS)
## QueryMate: AI Healthcare Question Answering Chatbot

- **Version:** 1.0
- **Status:** Draft for review
- **Related document:** `01_BRD.md`

## 1. Purpose
Define observable system behavior and quality requirements for the QueryMate prototype.

## 2. Product overview
A web-based chatbot accepts an English healthcare question, checks input and risk indicators, retrieves relevant material from an approved local dataset/index, and returns a response or safe fallback. A generative model is optional and must be evaluated before inclusion.

## 3. User classes
- **Visitor/user:** submits questions and reads responses.
- **Project maintainer:** runs the application, updates the dataset/index, and reviews evaluation results.
- **Evaluator:** uses a test set to rate relevance, readability, grounding, and safety.

## 4. Functional requirements
| ID | Requirement | Priority | Verification |
|---|---|---|---|
| FR-01 | The system shall accept a non-empty text question. | Must | UI test |
| FR-02 | The system shall reject or explain empty submissions. | Must | UI test |
| FR-03 | The system shall normalize text without changing medical meaning. | Must | Unit tests / review |
| FR-04 | The system shall retrieve one or more relevant dataset entries or produce a documented fallback. | Must | Retrieval test |
| FR-05 | The system shall display an answer clearly associated with the user's question. | Must | UI test |
| FR-06 | The interface shall display a visible healthcare disclaimer. | Must | UI review |
| FR-07 | The system shall use a safe fallback when retrieval confidence is below a validated threshold. | Must | Threshold test |
| FR-08 | The system shall provide safety-oriented guidance for recognized emergency indicators. | Must | Safety test set |
| FR-09 | The system shall not present the output as a confirmed diagnosis. | Must | Safety review |
| FR-10 | The system shall allow the user to clear/reset the current session. | Should | UI test |
| FR-11 | The system should support related follow-up questions if conversation context is implemented. | Should | Conversation test |
| FR-12 | The system should collect optional answer feedback without requiring personal details. | Could | UI test |
| FR-13 | The system shall handle model/index errors without exposing secrets or stack traces to the user. | Must | Failure test |
| FR-14 | The system shall not persist chat history by default unless explicitly configured and disclosed. | Must | Privacy/config test |

## 5. Non-functional requirements
| ID | Requirement | Target / notes |
|---|---|---|
| NFR-01 Usability | Core chat workflow should be understandable without training. |
| NFR-02 Performance | Preferred response time ≤ 5 seconds on documented test hardware; report actual percentiles. |
| NFR-03 Reliability | Errors should produce a graceful fallback rather than a crash. |
| NFR-04 Privacy | Minimize personal data collection and avoid unnecessary storage of health text. |
| NFR-05 Security | Keep API keys in environment variables/secrets; never commit credentials. |
| NFR-06 Maintainability | Separate UI, retrieval, safety, and configuration into modules where practical. |
| NFR-07 Transparency | State intended use, limitations, and when professional care is needed. |
| NFR-08 Portability | Setup steps and dependencies must be documented. |
| NFR-09 Accessibility | Provide readable contrast, labels, keyboard-operable controls, and clear error messages. |

## 6. Inputs and outputs
### Input
- A text string containing a general healthcare question.
- Optional session context, if supported.

### Output
- A response text.
- Optional indication that the answer is based on retrieved material.
- A safety message or fallback when appropriate.
- No guarantee of diagnosis, treatment, or correctness.

## 7. Error handling
- Empty input: ask the user to enter a question.
- Unsupported/low-confidence question: state the limitation and recommend a qualified professional when appropriate.
- Model/index unavailable: show a short service error and avoid fabricated output.
- Potential emergency: prioritize concise emergency guidance rather than normal Q&A.
- Unexpected backend error: log minimal technical details without sensitive conversation content.

## 8. Acceptance criteria
1. A valid question can be submitted and receives a response or explicit safe fallback.
2. Empty input is not processed.
3. Disclaimer is visible in the main chat experience.
4. Low-confidence retrieval triggers fallback at a threshold selected through validation.
5. A defined set of emergency test prompts triggers the safety path.
6. No credentials appear in source control.
7. A reset action clears session conversation state.
8. Evaluation results can be reproduced from documented instructions.

## 9. Dependencies
Python environment, chosen NLP/retrieval libraries, dataset file and its license, optional embedding model/LLM, and chosen UI framework.

## 10. Open decisions
- Final frontend/backend stack.
- Exact retrieval model and confidence threshold.
- Whether RAG/LLM generation is feasible and justified.
- Whether chat context is maintained only in session.
- Hosting and deployment environment.
