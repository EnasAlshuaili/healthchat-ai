# QueryMate — AI Healthcare Question Answering Chatbot
## Project Documentation Pack

This folder contains the core planning, design, data, AI, safety, testing, and delivery documents for **QueryMate**, an English-language AI healthcare question-answering prototype.

## Files
1. `01_BRD.md` — business needs, goals, scope, stakeholders, and success measures.
2. `02_SRS.md` — functional/non-functional requirements and acceptance criteria.
3. `03_System_Design.md` — proposed architecture, components, data flow, and interfaces.
4. `04_Dataset_Analysis.md` — dataset profile, audit plan, cleaning, and leakage controls.
5. `05_AI_NLP_Model_Report.md` — candidate approaches, experiment plan, metrics, and model-selection rules.
6. `06_UI_UX_Design.md` — screens, user journeys, content, and interaction requirements.
7. `07_Safety_and_Risk_Assessment.md` — healthcare safety controls, risks, and mitigations.
8. `08_Testing_Plan.md` — test strategy, test cases, and release gates.
9. `09_Project_Plan.md` — phases, work packages, and deliverables.
10. `10_Final_Project_Report.md` — final report template to complete after implementation and evaluation.

## Project facts currently known
- Project name: **QueryMate: AI Healthcare Question Answering Chatbot**
- Primary dataset: `Doctor-HealthCare-100k.csv` (Kaggle dataset)
- Intended initial language: English
- Prototype direction: begin with retrieval-based NLP, then evaluate whether semantic embeddings/RAG are justified.
- Likely initial interface: Streamlit for a fast prototype. Confirm the stack before implementation.
- The chatbot is for general educational information only. It is not a diagnostic or treatment service.

## Dataset snapshot
{
  "filename": "Doctor-HealthCare-100k.csv",
  "rows": 112156,
  "columns": [
    "instruction",
    "input",
    "output"
  ],
  "missing": "To be measured during the dataset analysis phase",
  "duplicates": "To be measured during the dataset analysis phase",
  "language": "Expected to be primarily English; confirm during profiling",
  "missing_by_column": {
    "instruction": 0,
    "input": 0,
    "output": 0
  },
  "duplicate_rows": 0,
  "file_size_mb": 120.19,
  "sample_lengths": {
    "instruction": {
      "min": 92,
      "median": 92.0,
      "max": 92
    },
    "input": {
      "min": 1,
      "median": 351.0,
      "max": 11188
    },
    "output": {
      "min": 2,
      "median": 558.0,
      "max": 3304
    }
  }
}

## Important status note
This pack is a **planning baseline**, not evidence that the application has been implemented, clinically validated, or deployed. Items such as final architecture, model scores, response latency, dataset license, and clinical safety performance must be verified and updated based on actual work. Do not report proposed KPI targets as achieved results.

## Suggested working order
1. Review the BRD and SRS.
2. Confirm architecture and stack in the System Design.
3. Audit the dataset and its license.
4. Build a simple retrieval baseline.
5. Add safety handling and the interface.
6. Run the test plan and document actual results.
7. Complete the final report with real measurements.
