"""Tests for technical cleaning (step 3). Synthetic data, except the final checks,
which verify the generated processed file against the original CSV."""

import importlib.util
import json

import pandas as pd
import pytest

from querymate import audit, cleaning, config

FAKE_EMAIL = "jane.doe.clean@example.com"
FAKE_URL = "https://example.org/private-clean-page"
FAKE_PHONE = "+1 555 987 6543"
FAKE_NAME = "Ottoline Brackenbury"
DISTINCT_Q = "My aunt has a vexillological rash on her elbow since Tuesday"
DISTINCT_A = "Hi, a vexillological rash often improves with gentle care"
INSTR = "If you are a doctor, please answer the medical questions based on the patient's description."


@pytest.fixture
def raw_df():
    rows = [
        (f"Hi, my name is {FAKE_NAME}. {DISTINCT_Q}. Mail {FAKE_EMAIL} or {FAKE_URL}.",
         f"{DISTINCT_A}. Call {FAKE_PHONE}."),
        ("What  is   diabetes?", "Diabetes is a condition affecting blood sugar levels over time."),
        ("what is diabetes ?", "A different answer about diabetes and how it is managed long term."),
        ("Hello", "Brief Answer"),
        ("I have chest pain and shortness of breath.", "Take paracetamol 500\\u00a0mg twice daily and you may need anxiolytic Chat Doctor."),
        ("My wife has", "Hello"),
        ("Is the dose 5\\u00a0mg safe for my son?", "It\\u2019s best to ask, platelets 150000 200000 are noted."),
    ]
    return pd.DataFrame([(INSTR, q, a) for q, a in rows], columns=audit.EXPECTED_COLUMNS)


# --- Text-level rules --------------------------------------------------------

def test_decode_escaped_unicode_is_validated():
    text, dec, left = cleaning.decode_escaped_unicode("20\\u00a0mm, CO\\u2082, bad \\ud83d, ctrl \\u0007")
    assert text == "20 mm, CO₂, bad \\ud83d, ctrl \\u0007"
    assert dec == {"U+00A0": 1, "U+2082": 1}
    assert left == 2


def test_typography_and_whitespace_preserve_medical_content():
    t = cleaning.normalize_whitespace(cleaning.normalize_typography("Take  5 mg  of B12’s  (1.5 mL)  q8h; BP 120/80 mmHg. "))
    assert t == "Take 5 mg of B12's (1.5 mL) q8h; BP 120/80 mmHg."


def test_chat_doctor_and_medical_wording_untouched():
    text = "You may need anxiolytic Chat Doctor. Take amoxicillin 500 mg."
    assert cleaning.clean_text(text) == text


def test_redaction_of_contacts_but_not_numbers():
    text, ne, nu = cleaning.redact_contacts(f"Mail {FAKE_EMAIL}, see {FAKE_URL}. Platelets 150000 200000, call {FAKE_PHONE}.")
    assert (ne, nu) == (1, 1)
    assert text == f"Mail [EMAIL], see [URL]. Platelets 150000 200000, call {FAKE_PHONE}."


def test_question_usability_rules():
    assert cleaning.question_unusable("Hello")
    assert cleaning.question_unusable("My wife has")
    assert cleaning.question_unusable("")
    assert not cleaning.question_unusable("What is diabetes?")
    assert not cleaning.question_unusable("I have had a headache for three days now")


# --- DataFrame pipeline ------------------------------------------------------

def test_no_rows_deleted_and_traceability(raw_df):
    df, log = cleaning.clean_dataframe(raw_df)
    assert len(df) == len(raw_df)
    assert df["source_row"].tolist() == list(range(len(raw_df)))
    assert log["row_counts"]["rows_deleted"] == 0
    for i, row in df.iterrows():
        assert row["raw_input_sha256_16"] == cleaning.short_hash(raw_df.at[i, "input"])
        assert row["raw_output_sha256_16"] == cleaning.short_hash(raw_df.at[i, "output"])
        assert row["question"] == cleaning.clean_text(raw_df.at[i, "input"])
        assert row["answer"] == cleaning.clean_text(raw_df.at[i, "output"])
    assert "instruction" not in df.columns


def test_duplicates_conflicts_and_exclusions(raw_df):
    df, log = cleaning.clean_dataframe(raw_df)
    diabetes = df[df["question_norm_key"] == "what is diabetes"]
    assert len(diabetes) == 2
    assert diabetes["group_has_conflicting_answers"].all()
    assert diabetes["is_group_representative"].tolist() == [True, False]
    assert diabetes["exclusion_reason"].tolist() == ["", "E2_duplicate_question"]
    # Both distinct answers are kept unchanged.
    assert diabetes["answer"].nunique() == 2
    reasons = dict(zip(df["source_row"], df["exclusion_reason"]))
    assert reasons[3] == "E1_question_unusable"   # "Hello"
    assert reasons[5] == "E1_question_unusable"   # fragment
    assert log["retrieval_eligible_rows"] == 4
    funnel = log["retrieval_eligibility_funnel"]
    assert [f["rows_remaining"] for f in funnel] == [7, 5, 4]


def test_display_never_allowed(raw_df):
    df, log = cleaning.clean_dataframe(raw_df)
    assert not df["display_allowed"].any()
    assert log["display_policy"]["rows_display_allowed"] == 0


def test_flags_are_review_signals(raw_df):
    df, _ = cleaning.clean_dataframe(raw_df)
    by_row = df.set_index("source_row")
    assert by_row.at[0, "flag_q_email_address"] and by_row.at[0, "flag_q_url"]
    assert by_row.at[0, "flag_a_phone_like_number"]
    assert by_row.at[4, "flag_q_chest_pain"] and by_row.at[4, "flag_q_breathing_difficulty"]
    assert by_row.at[4, "flag_a_dose_amount"]  # detected only after escape decoding
    assert by_row.at[4, "flag_a_chat_doctor_possible_term_substitution"]
    assert by_row.at[3, "answer_unusable"]


def test_transformation_counts(raw_df):
    _, log = cleaning.clean_dataframe(raw_df)
    steps = {s["id"]: s for s in log["transformations"]}
    assert steps["T2"]["rows_affected_by_column"] == {"input": 1, "output": 2}
    assert steps["T2"]["decoded_code_points"] == {"U+00A0": 2, "U+2019": 1}
    assert steps["T4"]["rows_affected_by_column"]["input"] == 1
    assert steps["T6"]["replacements"] == {"email": 1, "url": 1}
    assert all(s["rows_before"] == s["rows_after"] == 7 for s in steps.values())


def test_cleaning_is_deterministic(raw_df):
    a, log_a = cleaning.clean_dataframe(raw_df)
    b, log_b = cleaning.clean_dataframe(raw_df.copy())
    pd.testing.assert_frame_equal(a, b)
    assert cleaning.content_hash(a) == cleaning.content_hash(b)
    assert log_a == log_b


def test_log_contains_no_raw_text_or_personal_data(raw_df):
    _, log = cleaning.clean_dataframe(raw_df)
    log["metadata"] = {"cleaning_version": "x"}
    rendered = json.dumps(log) + cleaning.render_markdown(log)
    for secret in [FAKE_EMAIL, FAKE_URL, FAKE_PHONE, FAKE_NAME, DISTINCT_Q, DISTINCT_A,
                   "vexillological", "Ottoline", "diabetes"]:
        assert secret not in rendered


def test_processed_text_has_no_redacted_contacts(raw_df):
    df, _ = cleaning.clean_dataframe(raw_df)
    blob = " ".join(df["question"]) + " ".join(df["answer"])
    assert FAKE_EMAIL not in blob and FAKE_URL not in blob


# --- Script-level tests ------------------------------------------------------

def _load_script():
    spec = importlib.util.spec_from_file_location(
        "run_cleaning", config.PROJECT_ROOT / "scripts" / "run_cleaning.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_script_leaves_source_unchanged_and_is_reproducible(raw_df, tmp_path):
    src = tmp_path / "raw" / "sample.csv"
    src.parent.mkdir()
    raw_df.to_csv(src, index=False)
    before, mtime = audit.sha256_file(src), src.stat().st_mtime_ns

    script = _load_script()
    log1 = script.run(src, tmp_path / "out1")
    log2 = script.run(src, tmp_path / "out2")

    assert audit.sha256_file(src) == before and src.stat().st_mtime_ns == mtime
    assert log1["metadata"]["input_sha256"] == before
    assert log1["metadata"]["output_content_sha256"] == log2["metadata"]["output_content_sha256"]
    assert log1["metadata"]["output_file_sha256"] == log2["metadata"]["output_file_sha256"]
    saved = pd.read_parquet(tmp_path / "out1" / "querymate_clean.parquet")
    assert len(saved) == len(raw_df)
    log_text = (tmp_path / "out1" / "cleaning_log.json").read_text(encoding="utf-8")
    log_text += (tmp_path / "out1" / "cleaning_log.md").read_text(encoding="utf-8")
    assert FAKE_EMAIL not in log_text and DISTINCT_Q not in log_text


def test_script_refuses_raw_directory(raw_df, tmp_path):
    src = tmp_path / "sample.csv"
    raw_df.to_csv(src, index=False)
    with pytest.raises(ValueError):
        _load_script().run(src, tmp_path)


# --- Real data: source integrity, traceability, and log privacy -------------

PROCESSED = config.PROCESSED_DIR / "querymate_clean.parquet"
LOG_JSON = config.PROCESSED_DIR / "cleaning_log.json"
needs_real = pytest.mark.skipif(
    not (config.RAW_DATA_PATH.exists() and PROCESSED.exists() and LOG_JSON.exists()),
    reason="raw dataset or processed outputs not present",
)


@pytest.fixture(scope="module")
def real():
    raw = audit.load_dataset_readonly(config.RAW_DATA_PATH)
    proc = pd.read_parquet(PROCESSED)
    log = json.loads(LOG_JSON.read_text(encoding="utf-8"))
    return raw, proc, log


@needs_real
def test_real_source_unchanged_and_log_metadata(real):
    raw, proc, log = real
    assert audit.sha256_file(config.RAW_DATA_PATH) == config.RAW_DATA_SHA256
    m = log["metadata"]
    assert m["input_sha256"] == config.RAW_DATA_SHA256
    assert m["output_file_sha256"] == audit.sha256_file(PROCESSED)
    assert m["output_content_sha256"] == cleaning.content_hash(proc)


@needs_real
def test_real_traceability(real):
    raw, proc, _ = real
    assert len(proc) == len(raw)
    assert proc["source_row"].tolist() == list(range(len(raw)))
    for i in range(0, len(raw), 997):
        row = proc.iloc[i]
        assert row["raw_input_sha256_16"] == cleaning.short_hash(raw.at[i, "input"])
        assert row["raw_output_sha256_16"] == cleaning.short_hash(raw.at[i, "output"])
        assert row["question"] == cleaning.clean_text(raw.at[i, "input"])
        assert row["answer"] == cleaning.clean_text(raw.at[i, "output"])


@needs_real
def test_real_display_never_allowed(real):
    _, proc, _ = real
    assert not proc["display_allowed"].any()


@needs_real
def test_real_log_contains_no_dataset_text(real):
    raw, _, _ = real
    text = LOG_JSON.read_text(encoding="utf-8")
    text += (config.PROCESSED_DIR / "cleaning_log.md").read_text(encoding="utf-8")
    checked = 0
    for col in audit.TEXT_COLS:
        for value in raw[col].iloc[::500]:
            if len(value) >= 80:
                mid = len(value) // 2
                assert value[mid - 20: mid + 20] not in text
                checked += 1
    assert checked > 300


def test_processed_outputs_are_gitignored():
    import subprocess
    for name in ["querymate_clean.parquet", "cleaning_log.json", "cleaning_log.md"]:
        r = subprocess.run(["git", "check-ignore", "-q", f"data/processed/{name}"], cwd=config.PROJECT_ROOT)
        assert r.returncode == 0, name
