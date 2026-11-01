# Healthcare Safety & Risk Assessment
## HealthChat AI: Educational Healthcare Q&A Chatbot

- **Version:** 1.0
- **Status:** Initial risk register; requires ongoing review

## 1. Intended use
Provide general, educational healthcare information in response to text questions. The prototype is not intended to diagnose, prescribe, replace clinical judgment, or manage emergencies.

### 1.1 Project context and review limitations
- HealthChat AI is a **solo educational portfolio project**. It is experimental and **not production-ready**.
- **No clinician reviewer is available.** No clinical review of the dataset, curated answers, safety rules, or test results has taken place.
- All reviews (dataset sampling, curated answers, safety test outcomes) are **non-clinical self-reviews by the developer**, recorded with reviewer and date.
- Raw dataset answers are never presented as trusted medical advice. Only curated answer text is displayed, and each curated entry must carry the label: *"Educational content written/reviewed by the developer. It has not undergone clinical review."*
- Potentially dangerous, urgent, or unsupported questions receive a safe fallback or generic emergency guidance instead of an answer.
- The project must not claim clinical validation, medical accuracy, or production readiness in the UI, README, report, or CV description.

## 2. Safety principles
1. Do not represent the system as a doctor.
2. Do not promise medical correctness.
3. Do not provide definitive diagnoses.
4. Avoid personalized medication/dosage instructions.
5. Prefer a safe fallback over a speculative answer.
6. For possible emergencies, prioritize immediate professional/emergency help.
7. Minimize personal and health data collection.
8. Test safety independently from general language quality.

## 3. Risk register
| ID | Hazard | Severity | Likelihood (initial) | Mitigation | Verification |
|---|---|---|---|---|---|
| R-01 | Incorrect answer causes harmful user action | Critical | Medium | Ground responses, low-confidence fallback, safety review | Human review and adversarial tests |
| R-02 | Emergency symptom is missed | Critical | Medium | Conservative safety pathway, curated test cases, clear escalation copy | Emergency test-set recall |
| R-03 | Model invents facts | High | Medium | Retrieval grounding, response checks, avoid unsupported generation | Groundedness review |
| R-04 | Unsafe medication advice | Critical | Medium | Disallow personalized dosage/prescription behavior; safety checks | Medication-focused tests |
| R-05 | User treats output as diagnosis | High | Medium | Persistent disclaimer and careful language | Usability testing |
| R-06 | Dataset answer is outdated or unsafe | High | Medium | License/provenance review and sampled content review | Dataset audit |
| R-07 | Sensitive text is stored or exposed | Critical | Low/Medium | No persistent chat storage by default; data minimization | Privacy/config review |
| R-08 | Dataset bias causes poor performance for some groups | High | Unknown | Evaluate diverse scenarios and document gaps | Stratified human review |
| R-09 | Similarity search returns irrelevant answer | High | Medium | Threshold calibration and fallback | Retrieval tests |
| R-10 | Safety checker fails or is bypassed | Critical | Low/Medium | Fail-safe design, tests, do not silently bypass | Failure injection |

Likelihood ratings are preliminary qualitative estimates, not measured probabilities.

## 4. Emergency handling
The prototype may detect a curated set of potentially urgent patterns (for example, severe chest pain, difficulty breathing, stroke-like symptoms, severe bleeding, loss of consciousness, or severe allergic reaction). These examples are not exhaustive and keyword matching is not clinically reliable.

When a possible emergency is detected:
- Show concise guidance to contact local emergency services or seek immediate professional care.
- Do not ask a long sequence of questions before displaying guidance.
- Do not claim to determine whether the user is safe.
- Do not substitute country-specific emergency numbers unless verified for the deployment location.
- For self-harm risk, provide immediate crisis/emergency guidance appropriate to the user's location where known and verified.

## 5. Medical content policy
- General educational information only.
- No definitive diagnosis.
- No prescription or individualized dosing.
- Do not recommend stopping prescribed treatment.
- Encourage consultation with a qualified professional for personal medical decisions.
- If symptoms are severe, worsening, or concerning, recommend professional evaluation.
- Avoid fabricated citations or claims that content was reviewed by a clinician if it was not.

## 6. Privacy controls
- Do not request names, national IDs, contact details, or medical record numbers.
- Do not store chat logs by default.
- If telemetry is needed, store aggregate operational metrics where possible.
- Keep API keys out of source control.
- Document any external API's data handling before sending health text to it.
- Provide notice if any data is stored or processed by a third party.

## 7. Safety evaluation set
Create manually reviewed examples for:
- General educational questions.
- Ambiguous symptom descriptions.
- Severe/emergency symptoms.
- Medication dosage requests.
- Requests for diagnosis.
- Contradictory or irrelevant questions.
- Low-resource/typo-heavy questions.
- Follow-up questions.
- Prompt-injection attempts that ask the model to ignore safety rules.

For each test, record expected safe behavior, actual output, pass/fail, reviewer, and date. Avoid putting real personal health information in the test set. Because no clinician is available, expected behaviors are defined and judged by the developer; this is recorded as a limitation of the safety evaluation.

## 8. Residual risks
Even with these controls, the system can produce unsafe or incomplete information. The UI must clearly state that the system is an educational prototype. Do not deploy for clinical decision-making without qualified clinical, legal, privacy, security, and regulatory review.
