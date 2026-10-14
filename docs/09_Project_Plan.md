# Project Plan & Timeline
## QueryMate: AI Healthcare Question Answering Chatbot

- **Version:** 1.0
- **Status:** Proposed plan; dates to be confirmed

## 1. Delivery approach
Use iterative development: start with data understanding and a simple baseline, then add safety controls and interface features, and evaluate before presenting the prototype.

## 2. Work breakdown structure
| Phase | Tasks | Deliverable | Exit criteria |
|---|---|---|---|
| 1. Requirements | Review BRD/SRS, finalize scope and stack | Approved requirements | Open decisions recorded |
| 2. Dataset audit | Inspect schema, missing values, duplicates, license, answer quality | Dataset report | Data limitations documented |
| 3. Baseline NLP | Build TF-IDF retrieval baseline | Working baseline | Repeatable query-to-answer demo |
| 4. Evaluation set | Prepare normal, unrelated, ambiguous, and safety prompts | Test set | Expected behavior recorded |
| 5. Model comparison | Compare baseline with embeddings if feasible | Experiment report | Evidence-based model choice |
| 6. Safety layer | Emergency-oriented route, low-confidence fallback, disclaimer | Safety module | Safety tests run |
| 7. UI | Build chat interface and session reset | Working interface | Core user journey works |
| 8. Integration | Connect UI, retrieval, safety, configuration | Integrated prototype | End-to-end tests pass |
| 9. Evaluation | Run quality, safety, and latency tests | Results report | Failures and limitations documented |
| 10. Finalization | Documentation, demo, final report | Final project pack | Deliverables reviewed |

## 3. Suggested schedule
Use relative weeks until a deadline is confirmed:
| Week | Focus |
|---|---|
| Week 1 | Requirements review, dataset profiling, license check |
| Week 2 | Data cleaning and TF-IDF baseline |
| Week 3 | Test set, baseline evaluation, threshold tuning |
| Week 4 | Optional embeddings/RAG comparison |
| Week 5 | Safety layer and UI |
| Week 6 | Integration, functional tests, safety tests |
| Week 7 | Fixes, performance checks, final evaluation |
| Week 8 | Final report, demo, presentation |

This is a planning estimate, not a commitment. Adjust based on academic deadlines, team size, and compute availability.

## 4. Roles
If working individually, one person may cover all roles. For a team, assign:
- Project lead/documentation.
- Data/NLP developer.
- UI/integration developer.
- Testing and safety reviewer.
- Supervisor/reviewer.

Do not assume clinical review unless a qualified reviewer has actually completed it.

## 5. Dependencies
- Dataset availability and license review.
- Stable Python environment.
- Selected NLP library/model.
- Sufficient compute for chosen approach.
- Agreed evaluation questions.
- Optional external API approval if used.

## 6. Project risks
- Scope grows too large.
- Dataset license or quality is unsuitable.
- Model results are weaker than expected.
- Safety logic misses an important scenario.
- External API costs/privacy are unacceptable.
- Integration takes longer than expected.

Mitigate by prioritizing a simple retrieval baseline, limiting the MVP, testing early, and keeping a clear list of deferred features.

## 7. Change control
For any scope change, record:
- Requested change.
- Reason.
- Impact on timeline, architecture, safety, and evaluation.
- Decision and date.

## 8. Completion checklist
- [ ] Requirements reviewed.
- [ ] Dataset license/provenance documented.
- [ ] Data audit completed.
- [ ] Baseline implemented.
- [ ] Model choice justified by evaluation.
- [ ] Safety controls tested.
- [ ] UI integrated.
- [ ] Test results documented.
- [ ] Known limitations documented.
- [ ] Final report and demo prepared.
