"""Deterministic technical cleaning of the HealthChat AI dataset.

Principles (see docs/DECISIONS.md D-01, D-08):
- The original CSV is never modified; every processed row keeps its source row index
  and hashes of its original text for traceability.
- Only technical, meaning-preserving transformations are applied. Medical wording,
  "Chat Doctor" placeholders, and apparent truncation are flagged, never rewritten.
- No rows are deleted. Records unsuitable for retrieval experiments are marked with
  an exclusion reason instead.
- Technical cleaning is separate from display decisions: no dataset answer is
  approved for display (`display_allowed` is always False).
- Review-signal flags are approximate heuristics, not clinical or privacy classifications.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter

import pandas as pd

from querymate import audit

CLEANING_VERSION = "1.0.0"

Q, A = audit.QUESTION_COL, audit.ANSWER_COL

# --- Text transformations ---------------------------------------------------

ESCAPED_UNICODE = re.compile(r"\\u([0-9a-fA-F]{4})")
TYPOGRAPHIC_MAP = str.maketrans({
    " ": " ",   # no-break space -> space
    "‘": "'",   # left single quotation mark
    "’": "'",   # right single quotation mark / apostrophe
    "“": '"',   # left double quotation mark
    "”": '"',   # right double quotation mark
})
WHITESPACE_RUN = re.compile(r"\s+")
EMAIL = re.compile(audit.PRIVACY["email_address"], re.IGNORECASE)
URL = re.compile(r"(?:https?://|\bwww\.)\S+", re.IGNORECASE)
URL_TRAILING_PUNCT = re.compile(r"[.,;:!?)\]]+$")

EMAIL_TOKEN = "[EMAIL]"
URL_TOKEN = "[URL]"


def decode_escaped_unicode(text: str) -> tuple[str, Counter, int]:
    """Decode literal '\\uXXXX' sequences into the character they encode.

    Only valid, non-surrogate, non-control code points are decoded; anything else
    is left unchanged. Returns (text, Counter of decoded code points, n_left_undecoded).
    """
    decoded: Counter = Counter()
    left = 0

    def repl(m: re.Match) -> str:
        nonlocal left
        cp = int(m.group(1), 16)
        ch = chr(cp)
        if 0xD800 <= cp <= 0xDFFF or unicodedata.category(ch).startswith("C"):
            left += 1
            return m.group(0)
        decoded[f"U+{cp:04X}"] += 1
        return ch

    return ESCAPED_UNICODE.sub(repl, text), decoded, left


def normalize_typography(text: str) -> str:
    return text.translate(TYPOGRAPHIC_MAP)


def normalize_whitespace(text: str) -> str:
    return WHITESPACE_RUN.sub(" ", text).strip()


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def redact_contacts(text: str) -> tuple[str, int, int]:
    """Replace email addresses and URLs with placeholder tokens.

    Phone-like numbers are deliberately NOT redacted: the same digit pattern
    matches sequences of lab values, which would alter medical content.
    """
    text, n_email = EMAIL.subn(EMAIL_TOKEN, text)

    def url_repl(m: re.Match) -> str:
        trail = URL_TRAILING_PUNCT.search(m.group(0))
        return URL_TOKEN + (trail.group(0) if trail else "")

    text, n_url = URL.subn(url_repl, text)
    return text, n_email, n_url


def clean_text(text: str) -> str:
    """Apply transformations T2-T6 to a single text, in pipeline order."""
    text, _, _ = decode_escaped_unicode(text)
    text = normalize_unicode(normalize_whitespace(normalize_typography(text)))
    text, _, _ = redact_contacts(text)
    return text


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# --- Record-level rules -----------------------------------------------------

MIN_QUESTION_WORDS = 3
SHORT_QUESTION_CHARS = 20
MIN_ANSWER_CHARS = 40


def question_unusable(question: str) -> bool:
    """Question cannot serve as a retrieval key: empty, greeting-only, fewer than
    3 words, a short fragment without a question mark, or no common English words."""
    words = question.split()
    return (
        not question
        or audit.GREETING_ONLY_QUESTION.fullmatch(question) is not None
        or len(words) < MIN_QUESTION_WORDS
        or (len(question) < SHORT_QUESTION_CHARS and not question.endswith("?"))
        or audit.COMMON_ENGLISH.search(question) is None
    )


def answer_unusable(answer: str) -> bool:
    """Answer has no substantive content: empty, header-only, or under 40 characters."""
    return (
        len(answer) < MIN_ANSWER_CHARS
        or audit.HEADER_ONLY_ANSWER.fullmatch(answer) is not None
    )


# Review-signal flags: (column name, audit pattern group, pattern name, source column).
# Computed on whitespace-normalised text *before* redaction so privacy flags reflect the source.
FLAG_SPECS = (
    [(f"flag_q_{n}", "emergency_related_questions", n, Q) for n in audit.EMERGENCY_QUESTION]
    + [(f"flag_q_{n}", "population_context", n, Q) for n in audit.POPULATION_CONTEXT]
    + [(f"flag_{c}_{n}", "privacy_indicators", n, col)
       for c, col in (("q", Q), ("a", A))
       for n in ["email_address", "url", "phone_like_number", "self_identified_name",
                 "named_doctor_salutation", "date_like"]]
    + [(f"flag_a_{n}", "medical_risk_indicators", n, A) for n in audit.MEDICAL_RISK]
    + [(f"flag_a_{n}", "placeholders", n, A) for n in audit.PLACEHOLDERS]
)


def _flag_column(texts: list[str], lowered: list[str], group: str, name: str) -> list[bool]:
    rx, use_lower = audit._COMPILED[group][name]
    src = lowered if use_lower else texts
    return [rx.search(t) is not None for t in src]


COLUMN_DESCRIPTIONS = {
    "source_row": "0-based data-row index in the original CSV (header excluded). Primary traceability key.",
    "raw_input_sha256_16": "First 16 hex chars of SHA-256 of the original `input` text.",
    "raw_output_sha256_16": "First 16 hex chars of SHA-256 of the original `output` text.",
    "question": "Technically cleaned question (from `input`).",
    "answer": "Technically cleaned answer (from `output`). UNVERIFIED; not approved for display.",
    "question_norm_key": "Lowercased, alphanumeric-only question used for duplicate grouping.",
    "question_group_id": "Group of rows sharing the same normalised question (ids in first-appearance order).",
    "question_group_size": "Number of rows in the question group.",
    "is_group_representative": "True for the first usable row of each question group.",
    "group_has_conflicting_answers": "True if the group's rows have more than one distinct normalised answer. Answers are never merged.",
    "is_duplicate_pair": "True if another earlier row has identical cleaned question and answer.",
    "question_word_count": "Whitespace-delimited word count of the cleaned question.",
    "answer_word_count": "Whitespace-delimited word count of the cleaned answer.",
    "escapes_decoded": "Number of literal \\uXXXX escapes decoded in this row.",
    "contacts_redacted": "Number of email/URL redactions in this row.",
    "question_unusable": "Question unsuitable as a retrieval key (see cleaning log rule E1).",
    "answer_unusable": "Answer has no substantive content (empty, header-only, < 40 chars). Review signal only.",
    "retrieval_eligible": "True if the row may be indexed in retrieval experiments.",
    "exclusion_reason": "Why the row is not retrieval-eligible ('' if eligible).",
    "display_allowed": "Always False: dataset answers are unreviewed and must not be shown to users (D-01).",
    "flag_*": "Approximate regex review signals (see audit pattern definitions). Not clinical or privacy classifications.",
}


# --- Pipeline ---------------------------------------------------------------

def clean_dataframe(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Return (processed DataFrame, log dict of aggregated statistics)."""
    missing = [c for c in audit.EXPECTED_COLUMNS if c not in raw.columns]
    if missing:
        raise ValueError(f"Dataset is missing expected columns: {missing}")

    n = len(raw)
    steps: list[dict] = []

    def step(sid, name, rationale, affected, columns, **extra):
        steps.append({"id": sid, "name": name, "rationale": rationale, "columns": columns,
                      "rows_before": n, "rows_after": n, "rows_affected": int(affected), **extra})

    df = pd.DataFrame({
        "source_row": range(n),
        "raw_input_sha256_16": [short_hash(t) for t in raw[Q]],
        "raw_output_sha256_16": [short_hash(t) for t in raw[A]],
    })
    step("T0", "Assign traceability identifiers",
         "Keep the 0-based source row index and hashes of the original text so every processed record maps back to the unmodified CSV.",
         n, ["source_row", "raw_input_sha256_16", "raw_output_sha256_16"])

    instr_values = raw["instruction"].unique().tolist()
    step("T1", "Drop `instruction` column",
         "Constant role-play prompt with no retrieval value; it also frames answers as from a doctor, which the project must not do.",
         n, ["instruction"], unique_values=len(instr_values))

    texts = {c: raw[c].tolist() for c in (Q, A)}

    # T2: decode literal \uXXXX escapes
    decoded_total: Counter = Counter()
    left_total = 0
    escapes_per_row = [0] * n
    affected = {Q: 0, A: 0}
    for c in (Q, A):
        out = []
        for i, t in enumerate(texts[c]):
            new, dec, left = decode_escaped_unicode(t)
            if dec:
                affected[c] += 1
                escapes_per_row[i] += sum(dec.values())
            decoded_total += dec
            left_total += left
            out.append(new)
        texts[c] = out
    step("T2", "Decode literal \\uXXXX escapes",
         "Escapes are serialisation artefacts; decoding restores the exact intended character (e.g. '20\\u00a0mm' -> '20 mm'). Surrogates and control characters are left untouched.",
         affected[Q] + affected[A], [Q, A],
         rows_affected_by_column=affected,
         decoded_code_points=dict(sorted(decoded_total.items(), key=lambda kv: (-kv[1], kv[0]))),
         escapes_left_undecoded=left_total)

    def apply(sid, name, rationale, fn):
        aff = {}
        for c in (Q, A):
            new = [fn(t) for t in texts[c]]
            aff[c] = sum(a != b for a, b in zip(new, texts[c]))
            texts[c] = new
        step(sid, name, rationale, aff[Q] + aff[A], [Q, A], rows_affected_by_column=aff)

    apply("T3", "Normalise typographic characters",
          "No-break spaces become spaces; curly quotes become ASCII quotes. Punctuation meaning is unchanged; units, numbers, and other symbols are preserved.",
          normalize_typography)
    apply("T4", "Normalise whitespace",
          "Collapse runs of whitespace to a single space and strip ends. The source has no newlines or tabs, so no structure is lost.",
          normalize_whitespace)
    apply("T5", "Unicode NFC normalisation",
          "Canonical composition only (not NFKC), so characters such as subscripts and symbols keep their form.",
          normalize_unicode)

    # Review-signal flags on the pre-redaction text.
    lowered = {c: [t.lower() for t in texts[c]] for c in (Q, A)}
    flags = {col: _flag_column(texts[src], lowered[src], g, name) for col, g, name, src in FLAG_SPECS}

    # T6: redact emails and URLs.
    red_aff = {}
    red_counts = {"email": 0, "url": 0}
    redactions_per_row = [0] * n
    for c in (Q, A):
        out, aff = [], 0
        for i, t in enumerate(texts[c]):
            new, ne, nu = redact_contacts(t)
            if ne or nu:
                aff += 1
                redactions_per_row[i] += ne + nu
            red_counts["email"] += ne
            red_counts["url"] += nu
            out.append(new)
        texts[c] = out
        red_aff[c] = aff
    step("T6", "Redact email addresses and URLs",
         "Contact details are not needed for retrieval and may identify people. Phone-like numbers are only flagged, because the pattern also matches sequences of lab values.",
         red_aff[Q] + red_aff[A], [Q, A], rows_affected_by_column=red_aff,
         replacements=red_counts, tokens=[EMAIL_TOKEN, URL_TOKEN])

    df["question"] = texts[Q]
    df["answer"] = texts[A]
    df["escapes_decoded"] = escapes_per_row
    df["contacts_redacted"] = redactions_per_row
    df["question_word_count"] = [len(t.split()) for t in texts[Q]]
    df["answer_word_count"] = [len(t.split()) for t in texts[A]]

    # --- Duplicates and conflicts (no text is merged or altered) ---
    df["question_norm_key"] = [audit.normalize_question(t) for t in texts[Q]]
    answer_keys = pd.Series([audit.normalize_question(t) for t in texts[A]])
    codes, _ = pd.factorize(df["question_norm_key"], sort=False)
    df["question_group_id"] = codes
    df["question_group_size"] = df.groupby("question_group_id")["source_row"].transform("size")
    distinct_answers = answer_keys.groupby(df["question_group_id"]).transform("nunique")
    df["group_has_conflicting_answers"] = distinct_answers.to_numpy() > 1
    df["is_duplicate_pair"] = df.duplicated(["question", "answer"], keep="first")

    # --- Usability and retrieval eligibility (question side only) ---
    df["question_unusable"] = [question_unusable(t) for t in texts[Q]]
    df["answer_unusable"] = [answer_unusable(t) for t in texts[A]]
    usable = ~df["question_unusable"]
    first_usable = df[usable].groupby("question_group_id")["source_row"].transform("min")
    df["is_group_representative"] = False
    df.loc[first_usable.index, "is_group_representative"] = (
        df.loc[first_usable.index, "source_row"] == first_usable
    )
    df["exclusion_reason"] = ""
    df.loc[df["question_unusable"], "exclusion_reason"] = "E1_question_unusable"
    df.loc[usable & ~df["is_group_representative"], "exclusion_reason"] = "E2_duplicate_question"
    df["retrieval_eligible"] = df["exclusion_reason"] == ""
    df["display_allowed"] = False

    for col in flags:
        df[col] = flags[col]

    ordered = (["source_row", "raw_input_sha256_16", "raw_output_sha256_16", "question", "answer",
                "question_norm_key", "question_group_id", "question_group_size",
                "is_group_representative", "group_has_conflicting_answers", "is_duplicate_pair",
                "question_word_count", "answer_word_count", "escapes_decoded", "contacts_redacted",
                "question_unusable", "answer_unusable", "retrieval_eligible", "exclusion_reason",
                "display_allowed"] + list(flags))
    df = df[ordered]

    log = _build_log(df, steps, n)
    return df, log


def _build_log(df: pd.DataFrame, steps: list[dict], n: int) -> dict:
    e1 = int((df["exclusion_reason"] == "E1_question_unusable").sum())
    e2 = int((df["exclusion_reason"] == "E2_duplicate_question").sum())
    eligible = int(df["retrieval_eligible"].sum())
    multi = df[df["question_group_size"] > 1]
    conflict_groups = df.loc[df["group_has_conflicting_answers"], "question_group_id"].nunique()

    return {
        "row_counts": {"source_rows": n, "processed_rows": int(len(df)), "rows_deleted": n - int(len(df))},
        "transformations": steps,
        "duplicates": {
            "question_groups_total": int(df["question_group_id"].nunique()),
            "groups_with_more_than_one_row": int(multi["question_group_id"].nunique()),
            "rows_in_multi_row_groups": int(len(multi)),
            "groups_with_conflicting_answers": int(conflict_groups),
            "rows_in_conflicting_groups": int(df["group_has_conflicting_answers"].sum()),
            "identical_question_answer_pairs_after_cleaning": int(df["is_duplicate_pair"].sum()),
            "handling": "Rows are never merged. One representative per normalised question is retrieval-eligible; "
                        "other rows are excluded (E2) but kept. Conflicting groups are flagged and answers are not treated as equivalent.",
        },
        "retrieval_eligibility_funnel": [
            {"step": "Start", "rows_remaining": n, "rows_excluded": 0},
            {"step": "E1 question unusable (empty, greeting-only, < 3 words, < 20-char fragment without '?', or no common English words)",
             "rows_remaining": n - e1, "rows_excluded": e1},
            {"step": "E2 duplicate normalised question (non-representative)",
             "rows_remaining": n - e1 - e2, "rows_excluded": e2},
        ],
        "retrieval_eligible_rows": eligible,
        "display_policy": {
            "rows_display_allowed": int(df["display_allowed"].sum()),
            "policy": "No dataset answer is approved for display (D-01). The processed dataset is for retrieval experiments only.",
        },
        "review_signals": {
            "answer_unusable": int(df["answer_unusable"].sum()),
            "answer_unusable_among_eligible": int((df["answer_unusable"] & df["retrieval_eligible"]).sum()),
            **{c: int(df[c].sum()) for c in df.columns if c.startswith("flag_")},
        },
        "not_performed": [
            "No replacement or removal of 'Chat Doctor' placeholders (meaning cannot be recovered; flagged instead).",
            "No spelling correction, lowercasing, stemming, or punctuation removal in stored text.",
            "No rewriting of medical wording, doses, units, or drug names.",
            "No completion of apparently truncated answers (flagged via audit 'dangling_ending' logic only).",
            "No merging of duplicate questions or their answers.",
            "No redaction of phone-like numbers, names, ages, or dates (flagged only).",
            "No row deletions.",
        ],
        "unresolved_issues": [
            "Answer text remains unverified and may contain unsafe advice, diagnostic certainty, or prescriptions.",
            "'Chat Doctor' substitutions corrupt part of the answer text; affected rows are flagged, not repaired.",
            "Names, ages, and phone-like numbers may remain in the text (flag counts above).",
            "Near-duplicate (paraphrased) questions are not grouped.",
            "Dataset license and provenance remain unverified (D-08).",
        ],
        "column_descriptions": COLUMN_DESCRIPTIONS,
    }


def content_hash(df: pd.DataFrame) -> str:
    """Order-sensitive hash of the processed content (independent of file encoding)."""
    row_hashes = pd.util.hash_pandas_object(df, index=True).to_numpy()
    return hashlib.sha256(row_hashes.tobytes()).hexdigest()


# --- Markdown rendering -----------------------------------------------------

def render_markdown(log: dict) -> str:
    m = log["metadata"]
    L = ["# Cleaning Log", "",
         "> Aggregated counts only; no questions or answers are reproduced. Flags are approximate review signals.", "",
         "## Metadata", "", "| Field | Value |", "|---|---|"]
    for k, v in m.items():
        L.append(f"| {k} | `{v}` |")
    rc = log["row_counts"]
    L += ["", "## Row counts", "",
          f"- Source rows: **{rc['source_rows']:,}**; processed rows: **{rc['processed_rows']:,}**; deleted: **{rc['rows_deleted']}**",
          "", "## Transformations", "",
          "| ID | Transformation | Rows before | Rows after | Rows affected | Rationale |",
          "|---|---|---:|---:|---:|---|"]
    for s in log["transformations"]:
        L.append(f"| {s['id']} | {s['name']} | {s['rows_before']:,} | {s['rows_after']:,} | {s['rows_affected']:,} | {s['rationale']} |")
    for s in log["transformations"]:
        extra = {k: v for k, v in s.items() if k not in {"id", "name", "rationale", "columns", "rows_before", "rows_after", "rows_affected"}}
        if extra:
            L += ["", f"**{s['id']} details:** " + "; ".join(f"{k} = {v}" for k, v in extra.items())]
    d = log["duplicates"]
    L += ["", "## Duplicates and conflicts", ""]
    L += [f"- {k}: {v:,}" if isinstance(v, int) else f"- {k}: {v}" for k, v in d.items()]
    L += ["", "## Retrieval-eligibility funnel", "", "| Step | Rows excluded | Rows remaining |", "|---|---:|---:|"]
    for f in log["retrieval_eligibility_funnel"]:
        L.append(f"| {f['step']} | {f['rows_excluded']:,} | {f['rows_remaining']:,} |")
    dp = log["display_policy"]
    L += ["", "## Display policy", "", f"- Rows allowed for display: **{dp['rows_display_allowed']}**", f"- {dp['policy']}",
          "", "## Review signals (row counts)", "", "| Signal | Rows |", "|---|---:|"]
    L += [f"| {k} | {v:,} |" for k, v in log["review_signals"].items()]
    L += ["", "## Not performed", ""] + [f"- {x}" for x in log["not_performed"]]
    L += ["", "## Unresolved issues", ""] + [f"- {x}" for x in log["unresolved_issues"]]
    L += ["", "## Data dictionary", "", "| Column | Description |", "|---|---|"]
    L += [f"| `{k}` | {v} |" for k, v in log["column_descriptions"].items()]
    return "\n".join(L) + "\n"
