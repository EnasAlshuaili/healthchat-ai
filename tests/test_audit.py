"""Tests for the dataset audit (step 2). Synthetic data only, except the final
checks, which inspect the generated report against the real dataset."""

import importlib.util
import json

import pandas as pd
import pytest

from querymate import audit, config

# Fake personal data that must never reach a report.
FAKE_EMAIL = "jane.doe.audit@example.com"
FAKE_URL = "https://example.org/private-page"
FAKE_PHONE = "+1 555 123 4567"
FAKE_NAME = "Zebulon Quartermaine"
DISTINCT_QUESTION = "My grandmother xylophonic tremor began after gardening"
DISTINCT_ANSWER = "Hello, the quixotic marmalade symptom usually settles"

INSTR = "If you are a doctor, please answer the medical questions based on the patient's description."


@pytest.fixture
def sample_df():
    rows = [
        (f"Hi, my name is {FAKE_NAME}. {DISTINCT_QUESTION}. Email {FAKE_EMAIL}",
         f"{DISTINCT_ANSWER}. Call {FAKE_PHONE} or see {FAKE_URL}."),
        ("I have severe chest pain and shortness of breath since an hour.",
         "Please go to the emergency department immediately."),
        ("What is diabetes?",
         "You may need anxiolytic Chat Doctor. Take care Chat Doctor."),
        ("What is diabetes?",  # duplicate question, different answer
         "Take paracetamol 500 mg twice daily for 5 days. If you have any doubts, ask."),
        ("what is   DIABETES",  # normalized duplicate
         "You have bacterial infection. It is due to the follicle size of 20\\u00a0mm and"),
        ("Hello", "Brief Answer"),
        ("   ", ""),
    ]
    return pd.DataFrame([(INSTR, q, a) for q, a in rows], columns=audit.EXPECTED_COLUMNS)


def _flag(report, group, col, name):
    return report[group][col][name]["count"]


def test_normalize_question():
    assert audit.normalize_question("  What IS   diabetes?? ") == "what is diabetes"


def test_missing_columns_raise():
    with pytest.raises(ValueError):
        audit.build_report(pd.DataFrame({"question": ["x"]}))


def test_schema_and_completeness(sample_df):
    r = audit.build_report(sample_df)
    assert r["schema"]["rows"] == 7
    assert r["schema"]["expected_columns_present"] is True
    assert r["schema"]["instruction_unique_values"] == 1
    assert r["completeness"]["input"]["whitespace_only"]["count"] == 1
    assert r["completeness"]["output"]["empty_string"]["count"] == 1


def test_duplicates_and_conflicts(sample_df):
    d = audit.build_report(sample_df)["duplicates"]
    assert d["exact_duplicate_rows"]["count"] == 0
    assert d["duplicate_questions_exact"]["count"] == 1
    assert d["duplicate_questions_normalized"]["count"] == 2
    assert d["conflicting_answers_exact_question"] == {
        "question_groups_with_multiple_distinct_answers": 1, "rows_in_those_groups": 2}
    assert d["conflicting_answers_normalized_question"] == {
        "question_groups_with_multiple_distinct_answers": 1, "rows_in_those_groups": 3}


def test_length_sections(sample_df):
    lengths = audit.build_report(sample_df)["lengths"]
    for col in audit.TEXT_COLS:
        assert set(lengths[col]["characters"]["percentiles"]) == {
            "p0", "p1", "p5", "p25", "p50", "p75", "p95", "p99", "p100"}
        assert sum(lengths[col]["character_histogram"].values()) == 7


def test_privacy_flags_count_without_values(sample_df):
    r = audit.build_report(sample_df)
    assert _flag(r, "privacy_indicators", "input", "email_address") == 1
    assert _flag(r, "privacy_indicators", "input", "self_identified_name") == 1
    assert _flag(r, "privacy_indicators", "output", "phone_like_number") == 1
    assert _flag(r, "privacy_indicators", "output", "url") == 1


def test_text_quality_flags(sample_df):
    r = audit.build_report(sample_df)
    assert _flag(r, "malformed_text", "output", "escaped_unicode_literal") == 1
    # Mid-sentence substitution is flagged; the "Take care Chat Doctor" sign-off is not.
    assert _flag(r, "placeholders", "output", "chat_doctor_possible_term_substitution") == 1
    assert _flag(r, "placeholders", "output", "chat_doctor_token_any") == 1
    sq = r["structure_quality"]
    assert sq["output"]["header_only"]["count"] == 1
    assert sq["output"]["dangling_ending"]["count"] == 1
    assert sq["input"]["greeting_only"]["count"] == 1


def test_medical_and_emergency_flags(sample_df):
    r = audit.build_report(sample_df)
    assert _flag(r, "medical_risk_indicators", "output", "dose_amount") >= 1
    assert _flag(r, "medical_risk_indicators", "output", "dosing_frequency") == 1
    assert _flag(r, "medical_risk_indicators", "output", "medication_name") == 1
    # "You have bacterial infection" is flagged; "If you have any doubts" is not.
    assert _flag(r, "medical_risk_indicators", "output", "diagnostic_certainty_language") == 1
    assert _flag(r, "emergency_related_questions", "input", "chest_pain") == 1
    assert _flag(r, "emergency_related_questions", "input", "breathing_difficulty") == 1
    assert r["medication_name_top_counts"]["output"] == {"paracetamol": 1}


def test_case_sensitive_patterns_use_original_text():
    rx, use_lower = audit._COMPILED["privacy_indicators"]["named_doctor_salutation"]
    assert use_lower is False
    rx, use_lower = audit._COMPILED["privacy_indicators"]["email_address"]
    assert use_lower is True


def test_report_is_deterministic(sample_df):
    assert audit.build_report(sample_df) == audit.build_report(sample_df.copy())


def test_report_contains_no_raw_text_or_personal_data(sample_df):
    report = audit.build_report(sample_df)
    report["metadata"] = {k: "x" for k in [
        "audit_version", "generated_at_utc", "input_path", "input_sha256",
        "sha256_matches_expected", "file_size_bytes", "file_size_mb",
        "python_version", "pandas_version"]}
    rendered = json.dumps(report) + audit.render_markdown(report)
    for secret in [FAKE_EMAIL, FAKE_URL, FAKE_PHONE, FAKE_NAME, DISTINCT_QUESTION,
                   DISTINCT_ANSWER, "xylophonic", "marmalade", "Zebulon"]:
        assert secret not in rendered


# --- Script-level tests (temporary synthetic CSV) ---------------------------

def _load_script():
    spec = importlib.util.spec_from_file_location(
        "run_audit", config.PROJECT_ROOT / "scripts" / "run_audit.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_script_leaves_input_unchanged_and_records_metadata(sample_df, tmp_path):
    src = tmp_path / "sample.csv"
    sample_df.to_csv(src, index=False)
    before = audit.sha256_file(src)
    mtime = src.stat().st_mtime_ns

    report = _load_script().run(src, tmp_path / "out")

    assert audit.sha256_file(src) == before
    assert src.stat().st_mtime_ns == mtime
    m = report["metadata"]
    assert m["input_sha256"] == before
    assert m["audit_version"] == audit.AUDIT_VERSION
    assert m["sha256_matches_expected"] is False  # synthetic file, not the original
    assert m["generated_at_utc"].endswith("Z")
    saved = (tmp_path / "out" / "dataset_audit.json").read_text(encoding="utf-8")
    assert FAKE_EMAIL not in saved and DISTINCT_QUESTION not in saved
    assert (tmp_path / "out" / "dataset_audit.md").exists()


def test_script_refuses_to_write_into_input_directory(sample_df, tmp_path):
    src = tmp_path / "sample.csv"
    sample_df.to_csv(src, index=False)
    with pytest.raises(ValueError):
        _load_script().run(src, tmp_path)


def test_script_reports_missing_input(tmp_path):
    with pytest.raises(FileNotFoundError):
        _load_script().run(tmp_path / "missing.csv", tmp_path / "out")


# --- Real dataset: source integrity and generated report contents -----------

REPORT_JSON = config.REPORTS_DIR / "dataset_audit.json"
needs_real_report = pytest.mark.skipif(
    not (config.RAW_DATA_PATH.exists() and REPORT_JSON.exists()),
    reason="raw dataset or generated audit report not present",
)


@needs_real_report
def test_generated_report_matches_unchanged_source():
    assert audit.sha256_file(config.RAW_DATA_PATH) == config.RAW_DATA_SHA256
    meta = json.loads(REPORT_JSON.read_text(encoding="utf-8"))["metadata"]
    assert meta["input_sha256"] == config.RAW_DATA_SHA256
    assert meta["sha256_matches_expected"] is True


@needs_real_report
def test_generated_report_contains_no_dataset_text():
    df = audit.load_dataset_readonly(config.RAW_DATA_PATH)
    text = REPORT_JSON.read_text(encoding="utf-8")
    text += (config.REPORTS_DIR / "dataset_audit.md").read_text(encoding="utf-8")
    checked = 0
    for col in audit.TEXT_COLS:
        for value in df[col].iloc[::500]:  # deterministic sample of ~225 rows per column
            if len(value) >= 80:
                mid = len(value) // 2
                assert value[mid - 20: mid + 20] not in text
                checked += 1
    assert checked > 300
