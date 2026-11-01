# Dataset Analysis & Preparation Report
## HealthChat AI: Educational Healthcare Q&A Chatbot

- **Source file:** `Doctor-HealthCare-100k.csv`
- **Status:** Initial automated profile where available; full content/medical-quality audit remains required.

## 1. Dataset purpose
The dataset is intended as a source of healthcare question-and-answer examples for prototyping NLP retrieval or a grounded question-answering workflow. Its entries must not be assumed to be clinically verified or current.

## 2. Initial profile
```json
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
```

If the profile above says a value is unverified, run the profiling steps below against the exact project copy. If the schema differs from the expected `instruction`, `input`, `output` fields, update the pipeline and this report.

## 3. Data dictionary
| Field | Expected meaning | Audit notes |
|---|---|---|
| `instruction` | Instruction/prompt describing the requested response style | Review consistency and whether it adds useful information. |
| `input` | Patient question or healthcare prompt | Main retrieval query field; inspect blank/very short/very long entries. |
| `output` | Doctor-style response | Review safety, relevance, length, and unsupported treatment advice. |

## 4. Required quality checks
- Confirm column names and data types.
- Count rows and missing values per column.
- Count exact duplicate rows and duplicate questions.
- Identify empty/whitespace-only questions and answers.
- Review question and answer length distributions.
- Sample records from different length bands.
- Inspect language consistency.
- Check for personal information and other sensitive content.
- Review medication, dosage, diagnosis, and emergency-related content.
- Verify dataset license and permitted use before redistribution or deployment.
- Identify potentially stale, contradictory, or unsafe answers with a documented review sample.

## 5. Preprocessing plan
1. Preserve an untouched raw copy.
2. Normalize Unicode and whitespace carefully.
3. Remove records with missing question/answer after reviewing the count and impact.
4. Remove exact duplicates; investigate duplicate questions with conflicting answers.
5. Avoid aggressive cleaning that removes clinically meaningful punctuation, units, or dosage formatting.
6. Store a reproducible processed dataset with a data dictionary and processing log.
7. Do not use raw patient-identifiable data in a public demo.

## 6. Train/validation/test split
For a retrieval system, use a held-out evaluation set of questions that are not used to tune thresholds or index selection. Deduplicate before splitting and group near-duplicate questions where possible to reduce leakage.

A provisional split may be 80% development/training, 10% validation, 10% test, but the exact approach should reflect the chosen model. For pure retrieval, explain what is indexed and what is held out. Do not claim the split prevents all leakage without checking near-duplicates.

## 7. Data leakage and evaluation integrity
- Never evaluate on exact questions that were used to tune the same system without marking this as development data.
- Keep the final test set separate until the model/threshold is selected.
- If answers are retrieved from the dataset, explain that the reference answers may overlap with the index by design; construct a separate test protocol to measure retrieval/generalization honestly.
- Keep a fixed, versioned test set.

## 8. Medical safety review
The dataset's answer text is not automatically an approved medical source. Review a sample of outputs for:
- Definitive diagnosis language.
- Prescription or personalized dosage instructions.
- Advice that may delay emergency care.
- Unsupported certainty.
- Contradictions or missing caveats.
- Outdated recommendations.
Use a qualified healthcare reviewer if available; otherwise clearly document that review is educational and not clinical validation.

## 9. Dataset license and provenance
Before sharing the dataset or deploying a model trained on it:
- Record the Kaggle dataset page and author.
- Read the current license/terms.
- Record the download date and source version.
- Confirm whether redistribution, derivative datasets, and commercial use are permitted.
- Do not assume that availability on Kaggle means unrestricted use.

## 10. Analysis results
Measured by `scripts/run_audit.py` (audit v1.0.0) and `scripts/run_cleaning.py` (cleaning v1.0.0) on 2026-10-13/14. Full details: `reports/dataset_audit.md` and `data/processed/cleaning_log.md` (both generated, not committed).
| Metric | Result |
|---|---|
| Total rows | 112,156 |
| Total columns | 3 (`instruction`, `input`, `output`); `instruction` is a single constant value |
| Missing questions | 0 (no empty or whitespace-only values) |
| Missing answers | 0 |
| Exact duplicate rows | 0 |
| Duplicate questions | 154 exact, 217 normalised; 72 groups (289 rows), all with differing answers |
| Records removed | 0 deleted. 596 rows not retrieval-eligible: 554 unusable questions (E1), 42 duplicate questions (E2) |
| Technical transformations | Escape decoding (3,416 rows), typographic normalisation (2,829), whitespace (49,647), email/URL redaction (330) |
| Rows approved for display | 0 (D-01) |
| Language profile | All ASCII in source; heuristic English check only (486 questions lack common English words) |
| License verified | No, still pending (D-08) |
| Safety review sample size | Not yet performed (non-clinical self-review planned; no clinician available, D-11) |

## 11. Deliverables
- Dataset profiling notebook/script.
- Cleaned dataset or reproducible preparation script.
- Data dictionary.
- Cleaning log.
- License/provenance note.
- Data quality and safety review summary.
