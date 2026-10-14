"""Central paths and settings. Values can be overridden with environment variables."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_PATH = PROJECT_ROOT / os.getenv(
    "QUERYMATE_RAW_DATA", "data/raw/Doctor-HealthCare-100k.csv"
)
PROCESSED_DIR = DATA_DIR / "processed"
INDEX_DIR = DATA_DIR / "index"
EVAL_DIR = PROJECT_ROOT / "eval"
REPORTS_DIR = PROJECT_ROOT / "reports"

# SHA-256 of the original CSV as received (verified 2026-10-13). Used to confirm the raw file is unchanged.
RAW_DATA_SHA256 = "c1324260eaf0b08bd18762bd7de47794a7b611815cf8ce06f8cf8641648da51f"

MAX_INPUT_CHARS = int(os.getenv("QUERYMATE_MAX_INPUT_CHARS", "1000"))

# FR-14: no chat persistence by default.
STORE_CHATS = os.getenv("QUERYMATE_STORE_CHATS", "false").lower() == "true"
