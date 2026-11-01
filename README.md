# HealthChat AI — Educational Healthcare Q&A Chatbot

*Your AI Assistant for General Health Education.*

Educational prototype for **general healthcare information** in English.
HealthChat AI is **not** a doctor and does **not** diagnose, prescribe, or provide clinically validated triage.
Its emergency detection is a prototype safeguard only. It has not been clinically validated.

This is a **solo educational portfolio project** for learning NLP, Python, and Streamlit. It is experimental and not production-ready.
**No clinician has reviewed any part of it**; curated answers are educational content reviewed by the project owner, without clinical review.

> **Status:** Prototype components exist: a TF-IDF retrieval-ranking baseline (metadata only, no threshold selected), a curated-topic matcher (D-15), and a keyword-rule Safety & Scope Router v0.1.1 (D-17), each evaluated on the validation set only (provisional; not clinically validated). **The router and one curated topic are integrated:** the FastAPI backend sends every question through the router first. After `PROCEED` only, an exact lookup can return one owner-reviewed educational answer (hydration) with its sources; anything else gets the safe fallback (API contract v0.3, D-21). That answer has **not** been clinically reviewed or clinically validated. The topic matcher and the TF-IDF retrieval baseline are not connected; the router→matcher gate is unit-tested only. The React frontend (`frontend/`) calls this API through the local Vite dev proxy and shows the server's replies. The Streamlit UI is a mock-only preview with fixed placeholder replies and no backend connection (D-18). No dataset answer is approved for display (D-01).
> Formerly named QueryMate. The `querymate` Python package, `QUERYMATE_*` environment variables, and internal file names keep the old name on purpose (D-22).
>
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

## Dataset cleaning

```bash
.venv\Scripts\python.exe scripts\run_cleaning.py
```

Writes `data/processed/querymate_clean.parquet` plus `cleaning_log.json` / `cleaning_log.md` (about 2 minutes). Only technical, meaning-preserving cleaning is applied; no rows are deleted, and every row keeps its `source_row` index and hashes of the original text. The cleaned data is for retrieval experiments only: **no answer is approved for display** (`display_allowed` is always False).

## UI preview (mock only)

```bash
.venv\Scripts\python.exe -m streamlit run app.py
```

Opens at http://localhost:8501 (bound to localhost; usage statistics off). The interface is **not connected** to the safety router, topic matching, retrieval, or dataset: every assistant reply is a static, labelled mock placeholder from `src/querymate/ui/mock_responses.py` and never depends on the question. The sidebar's "UI state preview" switches which mock state (placeholder, no answer, emergency, error) is shown, for design review only.

## Local API (contract v0.3)

```bash
.venv\Scripts\python.exe scripts\run_api.py
```

Serves `GET /api/health` and `POST /api/chat` at http://127.0.0.1:8000 (localhost only, access log off), following [docs/API_CONTRACT.md](docs/API_CONTRACT.md) v0.3 (D-19, D-21). Every question goes through the Safety & Scope Router first (`src/querymate/pipeline.py`), and every reply is fixed text: safety and input-check messages, the safe fallback, or, for an exact approved question after `PROCEED`, the owner-reviewed hydration answer with its sources (`curated/topic_content.json`). That content is owner reviewed only: it has not been clinically reviewed or clinically validated. The router is a keyword prototype, not clinical triage, and is not clinically validated. The API is not connected to topic matching, the TF-IDF retrieval baseline, or the dataset, and never returns dataset answers.

## Project layout

```text
app.py                 Streamlit entry point (mock-only UI preview, D-18)
app_pages/             Streamlit pages (chat, how it works, about)
src/querymate/         Application package (config, preprocessing, retrieval, safety, ...)
src/querymate/api/     FastAPI layer (contract v0.3; D-19, D-21)
curated/               Topic catalogue and owner-reviewed educational content (D-15, D-21)
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
