"""Create the cleaned, traceable copy of the HealthChat AI dataset.

Usage (from the project root):
    .venv\\Scripts\\python.exe scripts\\run_cleaning.py [--input PATH] [--out-dir DIR]

Reads the original CSV read-only (SHA-256 checked before and after) and writes:
    data/processed/querymate_clean.parquet   cleaned rows + traceability + review flags
    data/processed/cleaning_log.json / .md   aggregated statistics only (no dataset text)
The processed data is for retrieval experiments only; no answer is approved for display.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from querymate import audit, cleaning, config  # noqa: E402

OUTPUT_NAME = "querymate_clean.parquet"


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(config.PROJECT_ROOT).as_posix()
    except ValueError:
        return path.name


def run(input_path: Path, out_dir: Path) -> dict:
    input_path = input_path.resolve()
    out_dir = out_dir.resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Dataset not found: {_display_path(input_path)}")
    if out_dir in {input_path.parent, config.RAW_DATA_PATH.parent.resolve()}:
        raise ValueError("Refusing to write processed data into the raw data directory.")

    started = time.perf_counter()
    stat_before = input_path.stat()
    hash_before = audit.sha256_file(input_path)

    raw = audit.load_dataset_readonly(input_path)
    processed, log = cleaning.clean_dataframe(raw)
    del raw

    if audit.sha256_file(input_path) != hash_before or input_path.stat().st_mtime_ns != stat_before.st_mtime_ns:
        raise RuntimeError("Input file changed during cleaning; outputs not written.")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / OUTPUT_NAME
    processed.to_parquet(out_file, index=False, engine="pyarrow")

    log = {
        "metadata": {
            "cleaning_version": cleaning.CLEANING_VERSION,
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "input_path": _display_path(input_path),
            "input_sha256": hash_before,
            "input_sha256_matches_expected": hash_before == config.RAW_DATA_SHA256,
            "output_path": _display_path(out_file),
            "output_file_sha256": audit.sha256_file(out_file),
            "output_content_sha256": cleaning.content_hash(processed),
            "python_version": platform.python_version(),
            "pandas_version": pd.__version__,
            "runtime_seconds": round(time.perf_counter() - started, 1),
        },
        **log,
    }
    (out_dir / "cleaning_log.json").write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "cleaning_log.md").write_text(cleaning.render_markdown(log), encoding="utf-8")
    return log


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, default=config.RAW_DATA_PATH)
    parser.add_argument("--out-dir", type=Path, default=config.PROCESSED_DIR)
    args = parser.parse_args()

    log = run(args.input, args.out_dir)
    m = log["metadata"]
    print(f"Cleaning v{m['cleaning_version']} complete in {m['runtime_seconds']}s")
    print(f"Rows: source={log['row_counts']['source_rows']:,} processed={log['row_counts']['processed_rows']:,} "
          f"retrieval_eligible={log['retrieval_eligible_rows']:,} display_allowed={log['display_policy']['rows_display_allowed']}")
    print(f"Input SHA-256 matches expected: {m['input_sha256_matches_expected']}")
    print(f"Output content SHA-256: {m['output_content_sha256']}")
    print(f"Wrote: {m['output_path']}, cleaning_log.json, cleaning_log.md")
    if not m["input_sha256_matches_expected"]:
        print("WARNING: input hash differs from the recorded original.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
