"""Reproducible, read-only audit of the original HealthChat AI dataset.

Usage (from the project root):
    .venv\\Scripts\\python.exe scripts\\run_audit.py [--input PATH] [--out-dir DIR]

Writes reports/dataset_audit.json and reports/dataset_audit.md. Reports contain
aggregated statistics only; no question or answer text is written or logged.
The input file is opened read-only and its SHA-256 is checked before and after.
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

from querymate import audit, config  # noqa: E402


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
    if out_dir == input_path.parent or out_dir == config.RAW_DATA_PATH.parent.resolve():
        raise ValueError("Refusing to write reports into the raw data directory.")

    started = time.perf_counter()
    stat_before = input_path.stat()
    hash_before = audit.sha256_file(input_path)

    df = audit.load_dataset_readonly(input_path)
    report = audit.build_report(df)
    del df

    hash_after = audit.sha256_file(input_path)
    stat_after = input_path.stat()
    if hash_after != hash_before or stat_after.st_mtime_ns != stat_before.st_mtime_ns:
        raise RuntimeError("Input file changed during the audit; results discarded.")

    report = {
        "metadata": {
            "audit_version": audit.AUDIT_VERSION,
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "input_path": _display_path(input_path),
            "input_sha256": hash_before,
            "expected_sha256": config.RAW_DATA_SHA256,
            "sha256_matches_expected": hash_before == config.RAW_DATA_SHA256,
            "file_size_bytes": stat_before.st_size,
            "file_size_mb": round(stat_before.st_size / (1024 * 1024), 2),
            "python_version": platform.python_version(),
            "pandas_version": pd.__version__,
            "runtime_seconds": round(time.perf_counter() - started, 1),
        },
        **report,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "dataset_audit.json").write_text(
        json.dumps(report, indent=2, sort_keys=False, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "dataset_audit.md").write_text(audit.render_markdown(report), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, default=config.RAW_DATA_PATH)
    parser.add_argument("--out-dir", type=Path, default=config.REPORTS_DIR)
    args = parser.parse_args()

    report = run(args.input, args.out_dir)
    m = report["metadata"]
    print(f"Audit v{m['audit_version']} complete in {m['runtime_seconds']}s")
    print(f"Input: {m['input_path']}  rows={report['schema']['rows']:,}")
    print(f"SHA-256: {m['input_sha256']}  matches expected: {m['sha256_matches_expected']}")
    print(f"Reports: {_display_path(args.out_dir)}/dataset_audit.json, dataset_audit.md")
    if not m["sha256_matches_expected"]:
        print("WARNING: input hash differs from the recorded original.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
