# QueryMate — AI Healthcare Question Answering Chatbot

Educational prototype for **general healthcare information** in English.
QueryMate is **not** a doctor and does **not** diagnose, prescribe, or provide clinically validated triage.
Its emergency detection is a prototype safeguard only.

This is a **solo educational portfolio project** for learning NLP, Python, and Streamlit. It is experimental and not production-ready.
**No clinician has reviewed any part of it**; any curated answers are educational content written by the developer without clinical review.

> **Status:** Step 2 of 7 (dataset audit). No retrieval, safety, or UI code yet.
> See [docs/DECISIONS.md](docs/DECISIONS.md) for approved decisions and [docs/](docs/) for the planning pack.

## Setup (Windows, Python 3.12)

```bash
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest
```

The system Python installation is not modified; all packages live in `.venv/`.

## Dataset

Place the original `Doctor-HealthCare-100k.csv` in `data/raw/` and **do not edit it**. Cleaning writes to `data/processed/`.

- License and provenance are **not yet verified**. Do not redistribute the dataset or deploy publicly until permitted use is established.
- Dataset files are gitignored and must never be committed.
- Dataset answers are unverified and are **not** shown to users directly.

## Dataset audit

```bash
.venv\Scripts\python.exe scripts\run_audit.py
```

Reads the raw CSV read-only (SHA-256 checked before and after) and writes aggregated statistics to `reports/dataset_audit.json` and `reports/dataset_audit.md`. No dataset text or personal data is written to the reports. Takes about 4 minutes.

## Project layout

```text
app.py                 Streamlit entry point (step 6)
src/querymate/         Application package (config, preprocessing, retrieval, safety, ...)
scripts/               Audit, cleaning, index-build, and evaluation scripts
tests/                 pytest suite
eval/                  Hand-written validation/test/safety question sets (no dataset content)
data/raw/              Original dataset (gitignored, unchanged)
data/processed/        Cleaned copy + cleaning log (gitignored)
data/index/            Generated retrieval index (gitignored)
reports/               Generated audit/evaluation outputs (gitignored)
docs/                  Planning and design documentation
```

## Privacy

No chat history is stored. No external AI services are used, and no questions or dataset content leave the machine.
