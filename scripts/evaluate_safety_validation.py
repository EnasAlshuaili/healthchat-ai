"""Validation-only baseline for the Safety & Scope Router (P9, P10).

Usage (from the project root):
    .venv\\Scripts\\python.exe scripts\\evaluate_safety_validation.py

Reads only eval/validation_questions.csv. Writes question IDs, routes, reason
codes, and outcomes (no question text) to the gitignored reports/ directory:
    safety_router_validation_v<version>.json
A report is written once per frozen router version and is never overwritten, so
the baseline stays separate from any later Validation-informed change.
n is small (5 emergency/crisis questions): these are smoke-test numbers, not
evidence of emergency recall or clinical safety.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from querymate import audit, config, retrieval_eval, safety, safety_eval  # noqa: E402


BASELINE_VERSION = "0.1.0"
KIND = {
    "0.1.0": "baseline: rules frozen before this run",
    "0.1.1": ("Validation-informed: rules changed after seeing the v0.1.0 baseline (D-17 amendment); "
              "NOT independent confirmation"),
}


def _report_path(version: str) -> Path:
    return config.REPORTS_DIR / f"safety_router_validation_v{version}.json"


def compare_with_baseline(results) -> list[dict]:
    """Per-ID route/outcome changes versus the v0.1.0 baseline report (IDs only)."""
    base = _report_path(BASELINE_VERSION)
    if safety.ROUTER_VERSION == BASELINE_VERSION or not base.exists():
        return []
    old = {r["question_id"]: r for r in json.loads(base.read_text(encoding="utf-8"))["per_question"]}
    changes = []
    for r in results.to_dict(orient="records"):
        o = old[r["question_id"]]
        if (o["route"], o["outcome"]) != (r["route"], r["outcome"]):
            changes.append({"question_id": r["question_id"], "route_before": o["route"], "route_after": r["route"],
                            "outcome_before": o["outcome"], "outcome_after": r["outcome"]})
    return changes


def main() -> int:
    out = _report_path(safety.ROUTER_VERSION)
    if out.exists():
        print(f"{out.name} already exists; a frozen version's report is not overwritten.")
        return 1
    if safety.ROUTER_VERSION not in KIND:
        print(f"No report label defined for router version {safety.ROUTER_VERSION}.")
        return 1
    results = safety_eval.evaluate(safety_eval.load_validation())
    s = safety_eval.summary(results)
    changes = compare_with_baseline(results)
    report = {
        "metadata": {
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "router_version": safety.ROUTER_VERSION,
            "rules_fingerprint": safety.rules_fingerprint(),
            "evaluation_file": "eval/validation_questions.csv",
            "evaluation_file_sha256": audit.sha256_file(retrieval_eval.VALIDATION_FILE),
            "test_set_used": False,
            "kind": KIND[safety.ROUTER_VERSION],
            "caveats": ["Prototype keyword router; not clinical triage; not clinically validated.",
                        "n = 5 emergency/crisis questions; smoke test only.",
                        "The rule author also wrote the evaluation sets (D-15(b)-style contamination); "
                        "results may be optimistic."],
        },
        "summary": s,
        "changes_vs_baseline_v" + BASELINE_VERSION: changes,
        "per_question": results.to_dict(orient="records"),
    }
    config.REPORTS_DIR.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"Router {safety.ROUTER_VERSION}: {KIND[safety.ROUTER_VERSION]}")
    print(json.dumps({k: v for k, v in s.items() if k != "route_by_expected_behavior"}, indent=1))
    print(f"Changes vs v{BASELINE_VERSION} baseline:")
    print(json.dumps(changes, indent=1))
    print(f"Wrote reports/{out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
