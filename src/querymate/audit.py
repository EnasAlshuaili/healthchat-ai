"""Aggregated, privacy-preserving dataset audit.

Every function here returns counts, percentages, or summary statistics only.
No question or answer text is ever placed in the report. Pattern flags are
approximate heuristics, not clinical or legal classifications.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

import pandas as pd

AUDIT_VERSION = "1.0.0"

EXPECTED_COLUMNS = ["instruction", "input", "output"]
QUESTION_COL = "input"
ANSWER_COL = "output"
TEXT_COLS = [QUESTION_COL, ANSWER_COL]

PERCENTILES = [0.0, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 1.0]
CHAR_BINS = [0, 20, 50, 100, 200, 500, 1000, 2000, 5000, float("inf")]

# Values pandas would treat as missing under default CSV parsing.
NA_LIKE_TOKENS = {"", "na", "n/a", "nan", "null", "none", "#n/a", "-nan", "<na>"}

# --- Pattern catalogue -------------------------------------------------------
# All patterns use non-capturing groups and are compiled case-insensitive;
# (?-i:...) marks case-sensitive parts. Each group is applied to the columns listed.

MALFORMED = {
    "escaped_unicode_literal": r"\\u[0-9a-f]{4}",
    "escaped_control_literal": r"\\[nrt](?![a-z])",
    "html_entity": r"&(?:[a-z]{2,8}|#\d{2,5});",
    "html_tag": r"</?(?:br|p|div|span|b|i|a|li|ul)\b[^>]{0,40}>",
    "mojibake_marker": r"â€|Ã[\x80-\xbf]|Â[\x80-\xbf ]",
    "control_character": r"[\x00-\x08\x0b\x0c\x0e-\x1f]",
    "non_ascii_character": r"[^\x00-\x7f]",
    "long_repeated_character_run": r"(?:([^\w\s])\1{5,})",
}

# Words that precede 'Chat Doctor' in greetings/sign-offs, where the token replaced a
# doctor's name or the site name ("I am Chat Doctor", "Take care Chat Doctor", "welcome to ...").
_CHAT_DOCTOR_BOILERPLATE = [
    "to", "using", "for", "on", "at", "from", "in", "by", "regards", "thanks", "care", "am",
    "choosing", "consulting", "visiting", "contacting", "writing", "with", "via", "is", "me",
    "query", "doctor", "dr", "calling", "asking",
]


def _not_preceded_by(words: list[str]) -> str:
    return "".join(rf"(?<!\b[{w[0].upper()}{w[0]}]{w[1:]})" for w in words)


PLACEHOLDERS = {
    "chat_doctor_token_any": r"chat\s*doctor",
    # 'Chat Doctor' directly after a lowercase word that is not greeting/sign-off
    # boilerplate: likely an anonymisation step that replaced a medical term
    # mid-sentence (e.g. a drug class or test name).
    "chat_doctor_possible_term_substitution": (
        r"(?-i:(?<=[a-z])" + _not_preceded_by(_CHAT_DOCTOR_BOILERPLATE) + r" Chat Doctor)\b"
    ),
}

PRIVACY = {
    "email_address": r"[a-z0-9._%+-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+",
    "url": r"https?://\S+|\bwww\.\S+",
    "phone_like_number": r"(?<!\d)\+?\d(?:[\s().-]?\d){9,}(?!\d)",
    "self_identified_name": r"\bmy name is\b",
    "named_doctor_salutation": r"(?-i:(?<!Chat )\b(?:Dr\.?|Doctor)\s+(?!Chat\b)[A-Z][a-z]{2,})",
    "age_mention": r"\b\d{1,3}\s*-?\s*(?:yrs?|years?)\b",
    "date_like": r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b",
}

MEDICATIONS = [
    "paracetamol", "acetaminophen", "ibuprofen", "diclofenac", "aspirin", "naproxen",
    "tramadol", "codeine", "morphine", "prednisolone", "prednisone", "dexamethasone",
    "hydrocortisone", "betahistine", "omeprazole", "pantoprazole", "ranitidine",
    "domperidone", "ondansetron", "metformin", "glimepiride", "amlodipine", "atenolol",
    "metoprolol", "losartan", "telmisartan", "atorvastatin", "levothyroxine", "thyroxine",
    "cetirizine", "levocetirizine", "montelukast", "salbutamol", "albuterol", "fluconazole",
    "clotrimazole", "acyclovir", "valacyclovir", "sertraline", "fluoxetine", "escitalopram",
    "alprazolam", "clonazepam", "diazepam", "gabapentin", "pregabalin", "warfarin",
    "clopidogrel", "progesterone", "clomiphene", "letrozole", "misoprostol", "levonorgestrel",
]
ANTIBIOTICS = [
    "antibiotics?", "amoxicillin", "amoxiclav", "augmentin", "azithromycin", "ciprofloxacin",
    "doxycycline", "metronidazole", "cefixime", "ceftriaxone", "cephalexin", "levofloxacin",
    "ofloxacin", "clindamycin", "linezolid", "nitrofurantoin",
]


def _word_list(words: list[str]) -> str:
    return r"\b(?:" + "|".join(words) + r")\b"


MEDICAL_RISK = {
    "medication_name": _word_list(MEDICATIONS),
    "antibiotic_mention": _word_list(ANTIBIOTICS),
    "dose_amount": r"\b\d+(?:\.\d+)?\s?(?:mg|mcg|µg|g|ml|iu|units?)\b",
    "dosing_frequency": (
        r"\b(?:once|twice|thrice|three times|four times)\s+(?:a|per)\s+day\b"
        r"|\b(?:once|twice) daily\b|\b(?:bd|bid|tds|tid|qid|qds)\b"
    ),
    "treatment_duration": r"\bfor\s+\d+\s*(?:days?|weeks?|months?)\b",
    "prescribing_language": (
        r"\b(?:take|start|use|prescribe|give|continue)\b[^.]{0,40}"
        r"\b(?:tablets?|tabs?|capsules?|caps?|syrup|injections?|ointment|cream|drops)\b"
    ),
    "stop_medication_language": (
        r"\b(?:stop|discontinue)\b[^.]{0,30}\b(?:medicines?|medications?|tablets?|drugs?|treatment)\b"
    ),
    "diagnostic_certainty_language": (
        r"\byou (?:definitely |clearly )?(?:have|are suffering from|are having) (?:got )?(?:an? )?"
        r"(?:\w+ )?\w*(?:itis|osis|oma|emia|aemia|infection|disease|syndrome|disorder|deficiency|cancer|tumou?r)\b"
        r"|\b(?:definitely|certainly|surely|clearly) (?:is|are|has|have|an?|due to|caused by|suffering from)\b"
        r"|\bthis is (?:a |an )?(?:case|sign|clear case) of\b"
        r"|\bit is (?:a case of|confirmed)\b"
    ),
    "hedged_diagnosis_language": (
        r"\b(?:most likely|probably|possibly|could be|may be due to|suggestive of)\b"
    ),
    "doctor_persona_language": (
        r"\bi am (?:a|an|your) (?:doctor|physician|surgeon|specialist)\b|\bas (?:a|your) doctor\b"
    ),
    "referral_language": (
        r"\b(?:consult|see a (?:doctor|physician|specialist)|visit (?:a|your) (?:doctor|physician)"
        r"|specialist|get (?:yourself )?(?:evaluated|examined))\b"
    ),
    "emergency_advice_language": (
        r"\bemergency\b|(?-i:\bER\b)|\bambulance\b|\bcall 911\b"
        r"|\bhospital (?:immediately|right away|at once)\b"
    ),
}

EMERGENCY_QUESTION = {
    "chest_pain": r"\bchest pain\b|\bpain in (?:my|the) chest\b",
    "breathing_difficulty": (
        r"\bshort(?:ness)? of breath\b|\bcan'?t breathe\b|\bdifficulty (?:in )?breathing\b"
        r"|\btrouble breathing\b"
    ),
    "stroke_like_symptoms": r"\bstroke\b|\bslurred speech\b|\bface (?:is )?droop|\bone side of (?:my|the|his|her) (?:body|face)\b",
    "self_harm_or_suicide": r"\bsuicid\w*|\bkill (?:my|him|her)self\b|\bself[- ]?harm\b|\bend my life\b",
    "overdose_or_poisoning": r"\boverdos\w*|\bpoison\w*",
    "severe_allergic_reaction": r"\banaphyla\w*|\bthroat (?:is )?(?:swelling|closing)\b",
    "severe_bleeding": r"\b(?:heavy|severe|profuse|uncontrolled) bleeding\b|\bvomiting blood\b|\bcoughing (?:up )?blood\b",
    "loss_of_consciousness": r"\bunconscious\b|\bpassed out\b|\bfainted\b|\bloss of consciousness\b",
    "seizure": r"\bseizures?\b|\bconvulsions?\b|\bfits?\b(?= (?:of|and|since|last|in))",
}

POPULATION_CONTEXT = {
    "pediatric_mention": r"\b(?:baby|infant|toddler|newborn|my (?:son|daughter|child|kid))\b|\b\d{1,2}\s*-?\s*months?\s*-?\s*old\b",
    "pregnancy_mention": r"\bpregnan\w*|\bweeks? pregnant\b|\btrimester\b",
}

PATTERN_GROUPS = {
    "malformed_text": MALFORMED,
    "placeholders": PLACEHOLDERS,
    "privacy_indicators": PRIVACY,
    "medical_risk_indicators": MEDICAL_RISK,
    "emergency_related_questions": EMERGENCY_QUESTION,
    "population_context": POPULATION_CONTEXT,
}
GROUP_COLUMNS = {
    "malformed_text": TEXT_COLS,
    "placeholders": TEXT_COLS,
    "privacy_indicators": TEXT_COLS,
    "medical_risk_indicators": TEXT_COLS,
    "emergency_related_questions": [QUESTION_COL],
    "population_context": [QUESTION_COL],
}

def _needs_original_case(pattern: str) -> bool:
    """True if the pattern has case-sensitive parts or non-ASCII uppercase literals."""
    return "(?-i:" in pattern or re.search(r"[À-Þ]", pattern) is not None


# Each entry: (compiled regex, match_on_lowercased_text). Matching pre-lowercased text
# without IGNORECASE is ~3x faster in CPython and gives identical results.
_COMPILED = {
    group: {
        name: (
            (re.compile(p, re.IGNORECASE | re.ASCII), False)
            if _needs_original_case(p)
            else (re.compile(p, re.ASCII), True)
        )
        for name, p in patterns.items()
    }
    for group, patterns in PATTERN_GROUPS.items()
}

HEADER_ONLY_ANSWER = re.compile(
    r"^(?:hi|hello|hey|greetings!?|dear\s+\w+|brief answer|detailed answer|short answer"
    r"|greetings!? answer|hello,?\s+(?:brief|short|detailed) answer)[\s.,!:]*$",
    re.IGNORECASE,
)
GREETING_ONLY_QUESTION = re.compile(
    r"^(?:hi|hello+|hey|good (?:morning|afternoon|evening)|(?:hi|hello) (?:doctor|dr|sir)"
    r"|dear (?:sir|doctor|dr))[\s.,!]*$",
    re.IGNORECASE,
)
COMMON_ENGLISH = re.compile(r"\b(?:the|i|my|is|and|have|a|to|of|it|in|for)\b", re.IGNORECASE | re.ASCII)
TERMINAL_PUNCT = re.compile(r"[.!?)\]\"']\s*$")
DANGLING_END = re.compile(r"(?:[,;:\-]|\b(?:and|or|the|to|of|with|a|an|is|but|for|in))\s*$", re.IGNORECASE | re.ASCII)
TAIL_CHARS = 40  # end-of-text checks only scan the final characters


# --- Helpers ----------------------------------------------------------------

def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def load_dataset_readonly(path: Path) -> pd.DataFrame:
    """Read the CSV through a read-only binary handle, keeping every value as text."""
    with open(path, "rb") as f:
        return pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8")


def normalize_question(text: str) -> str:
    """Lowercase, replace non-alphanumerics with spaces, collapse whitespace (for duplicate detection only)."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def _matches(texts, rx: re.Pattern, full: bool = False, tail: bool = False) -> int:
    """Count texts matching a compiled Python regex.

    Uses Python's `re` directly so results do not depend on the pandas string
    backend (pandas 3 Arrow strings use RE2, which lacks look-behind/back-references).
    `tail=True` starts the search near the end of each text (for `$`-anchored
    patterns); unlike slicing, `pos` keeps word boundaries correct.
    """
    if full:
        return sum(1 for t in texts if rx.fullmatch(t))
    if tail:
        return sum(1 for t in texts if rx.search(t, max(0, len(t) - TAIL_CHARS)))
    return sum(1 for t in texts if rx.search(t))


def _pct(n: int, total: int) -> float:
    return round(100.0 * n / total, 3) if total else 0.0


def _count(n: int, total: int) -> dict:
    return {"count": int(n), "pct": _pct(n, total)}


def _length_stats(lengths: pd.Series) -> dict:
    q = lengths.quantile(PERCENTILES)
    return {
        "mean": round(float(lengths.mean()), 1) if len(lengths) else 0.0,
        "std": round(float(lengths.std(ddof=0)), 1) if len(lengths) else 0.0,
        "percentiles": {f"p{int(p * 100)}": round(float(v), 1) for p, v in q.items()},
    }


def _histogram(lengths: pd.Series) -> dict:
    cut = pd.cut(lengths, bins=CHAR_BINS, right=False)
    counts = cut.value_counts(sort=False)
    out = {}
    for interval, n in counts.items():
        hi = "inf" if interval.right == float("inf") else int(interval.right)
        out[f"[{int(interval.left)}, {hi})"] = int(n)
    return out


# --- Report sections --------------------------------------------------------

def schema_section(df: pd.DataFrame) -> dict:
    instr = df["instruction"] if "instruction" in df.columns else pd.Series(dtype=str)
    return {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "column_count": int(df.shape[1]),
        "expected_columns_present": list(df.columns) == EXPECTED_COLUMNS,
        "dtypes_as_parsed": {c: "string" for c in df.columns},
        "dtype_note": "All columns read as text (dtype=str, no NA coercion) so no values are silently converted.",
        "instruction_unique_values": int(instr.nunique()),
    }


def completeness_section(df: pd.DataFrame) -> dict:
    n = len(df)
    out = {}
    for c in df.columns:
        s = df[c]
        stripped = s.str.strip()
        out[c] = {
            "empty_string": _count((s == "").sum(), n),
            "whitespace_only": _count(((stripped == "") & (s != "")).sum(), n),
            "na_like_token": _count(stripped.str.lower().isin(NA_LIKE_TOKENS - {""}).sum(), n),
        }
    return out


def duplicates_section(df: pd.DataFrame) -> dict:
    n = len(df)
    q, a = df[QUESTION_COL], df[ANSWER_COL]
    qn = q.map(normalize_question)
    an = a.map(normalize_question)

    def conflicts(keys: pd.Series, answers: pd.Series) -> dict:
        grp = pd.DataFrame({"k": keys, "a": answers}).groupby("k")["a"].nunique()
        bad = grp[grp > 1].index
        return {
            "question_groups_with_multiple_distinct_answers": int(len(bad)),
            "rows_in_those_groups": int(keys.isin(bad).sum()),
        }

    return {
        "exact_duplicate_rows": _count(df.duplicated().sum(), n),
        "duplicate_questions_exact": _count(q.duplicated().sum(), n),
        "duplicate_questions_normalized": _count(qn.duplicated().sum(), n),
        "duplicate_answers_exact": _count(a.duplicated().sum(), n),
        "duplicate_question_answer_pairs": _count(df.duplicated([QUESTION_COL, ANSWER_COL]).sum(), n),
        "conflicting_answers_exact_question": conflicts(q, a),
        "conflicting_answers_normalized_question": conflicts(qn, an),
        "normalization_note": "Normalized = lowercase, non-alphanumerics replaced by spaces, whitespace collapsed. Near-duplicate (paraphrase) detection is not performed.",
    }


def lengths_section(df: pd.DataFrame) -> dict:
    out = {}
    for c in TEXT_COLS:
        chars = df[c].str.len()
        words = df[c].str.split().str.len().fillna(0)
        out[c] = {
            "characters": _length_stats(chars),
            "words": _length_stats(words),
            "character_histogram": _histogram(chars),
        }
    return out


def pattern_section(df: pd.DataFrame, group: str) -> dict:
    n = len(df)
    out = {}
    for c in GROUP_COLUMNS[group]:
        original = df[c].tolist()
        lowered = [t.lower() for t in original]
        out[c] = {
            name: _count(_matches(lowered if use_lower else original, rx), n)
            for name, (rx, use_lower) in _COMPILED[group].items()
        }
    return out


def structure_quality_section(df: pd.DataFrame) -> dict:
    n = len(df)
    q = df[QUESTION_COL].str.strip()
    a = df[ANSWER_COL].str.strip()
    return {
        QUESTION_COL: {
            "very_short_lt_20_chars": _count((q.str.len() < 20).sum(), n),
            "greeting_only": _count(_matches(q, GREETING_ONLY_QUESTION, full=True), n),
            "no_common_english_function_words": _count(len(q) - _matches(q, COMMON_ENGLISH), n),
            "very_long_gt_2000_chars": _count((q.str.len() > 2000).sum(), n),
        },
        ANSWER_COL: {
            "very_short_lt_40_chars": _count((a.str.len() < 40).sum(), n),
            "header_only": _count(_matches(a, HEADER_ONLY_ANSWER, full=True), n),
            "no_terminal_punctuation": _count(len(a) - _matches(a, TERMINAL_PUNCT, tail=True), n),
            "dangling_ending": _count(_matches(a, DANGLING_END, tail=True), n),
        },
        "note": "'no_terminal_punctuation' over-counts truncation (sign-offs like 'Regards' also match); 'dangling_ending' is a stricter truncation signal.",
    }


def medication_name_counts(df: pd.DataFrame, top_n: int = 15) -> dict:
    """Rows mentioning each single-word medication name (one tokenisation pass per column)."""
    names = set(MEDICATIONS + ANTIBIOTICS[1:])
    word = re.compile(r"[a-z]+")
    out = {}
    for c in TEXT_COLS:
        counts = Counter()
        for t in df[c]:
            counts.update(names.intersection(word.findall(t.lower())))
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]
        out[c] = {name: n for name, n in ranked if n}
    return out


LIMITATIONS = [
    "All pattern flags are approximate regular-expression heuristics. They are not clinical, legal, or privacy classifications and have unmeasured false-positive and false-negative rates.",
    "Privacy indicators report counts only; they do not prove that personal data is (or is not) present.",
    "Medical-risk flags indicate wording that needs human review, not that an answer is unsafe or safe.",
    "Emergency-question flags are keyword matches and do not represent clinical triage.",
    "Duplicate detection covers exact and simple-normalized matches only; paraphrased near-duplicates are not detected.",
    "Language is profiled with ASCII and common-English-word heuristics only; no language-identification model is used.",
    "Dataset license and provenance are not verified by this audit.",
]


def build_report(df: pd.DataFrame) -> dict:
    """Return the aggregated audit metrics (deterministic for a given DataFrame)."""
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset is missing expected columns: {missing}")
    return {
        "schema": schema_section(df),
        "completeness": completeness_section(df),
        "duplicates": duplicates_section(df),
        "lengths": lengths_section(df),
        "structure_quality": structure_quality_section(df),
        **{group: pattern_section(df, group) for group in PATTERN_GROUPS},
        "medication_name_top_counts": medication_name_counts(df),
        "pattern_definitions": PATTERN_GROUPS,
        "limitations": LIMITATIONS,
    }


# --- Markdown rendering -----------------------------------------------------

def _flag_table(section: dict) -> list[str]:
    cols = list(section)
    names = list(section[cols[0]])
    lines = ["| Flag | " + " | ".join(f"{c} rows (%)" for c in cols) + " |",
             "|---|" + "---:|" * len(cols)]
    for name in names:
        cells = [f"{section[c][name]['count']:,} ({section[c][name]['pct']}%)" for c in cols]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return lines


def render_markdown(report: dict) -> str:
    m, s = report["metadata"], report["schema"]
    d = report["duplicates"]
    L = ["# Dataset Audit Report", "",
         "> Aggregated statistics only. No questions or answers are reproduced. "
         "Pattern flags are approximate heuristics, not clinical classifications.", "",
         "## Metadata", "",
         "| Field | Value |", "|---|---|"]
    for k in ["audit_version", "generated_at_utc", "input_path", "input_sha256",
              "sha256_matches_expected", "file_size_bytes", "file_size_mb",
              "python_version", "pandas_version"]:
        L.append(f"| {k} | `{m[k]}` |")

    L += ["", "## Schema", "",
          f"- Rows: **{s['rows']:,}**; columns: **{s['column_count']}** `{s['columns']}`",
          f"- Expected columns present: **{s['expected_columns_present']}**",
          f"- Types: {s['dtypes_as_parsed']} ({s['dtype_note']})",
          f"- Unique `instruction` values: **{s['instruction_unique_values']}**",
          "", "## Completeness", "",
          "| Column | Empty | Whitespace-only | NA-like token |", "|---|---:|---:|---:|"]
    for c, v in report["completeness"].items():
        L.append(f"| {c} | {v['empty_string']['count']:,} | {v['whitespace_only']['count']:,} | {v['na_like_token']['count']:,} |")

    L += ["", "## Duplicates", "", "| Metric | Count | % of rows |", "|---|---:|---:|"]
    for k, v in d.items():
        if isinstance(v, dict) and "count" in v:
            L.append(f"| {k} | {v['count']:,} | {v['pct']} |")
    for k in ["conflicting_answers_exact_question", "conflicting_answers_normalized_question"]:
        v = d[k]
        L.append(f"| {k}: groups / rows | {v['question_groups_with_multiple_distinct_answers']:,} / {v['rows_in_those_groups']:,} | |")
    L += ["", f"_{d['normalization_note']}_"]

    L += ["", "## Text lengths", "",
          "| Column | Unit | mean | p1 | p5 | p25 | p50 | p75 | p95 | p99 | max |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for c, v in report["lengths"].items():
        for unit in ["characters", "words"]:
            p = v[unit]["percentiles"]
            L.append(f"| {c} | {unit} | {v[unit]['mean']} | {p['p1']} | {p['p5']} | {p['p25']} | {p['p50']} | {p['p75']} | {p['p95']} | {p['p99']} | {p['p100']} |")
    L += ["", "Character-length histogram (rows per bin):", "",
          "| Bin | " + " | ".join(report["lengths"]) + " |", "|---|" + "---:|" * len(report["lengths"])]
    bins = list(next(iter(report["lengths"].values()))["character_histogram"])
    for b in bins:
        L.append(f"| {b} | " + " | ".join(f"{report['lengths'][c]['character_histogram'][b]:,}" for c in report["lengths"]) + " |")

    L += ["", "## Structure and completeness of text", ""]
    sq = report["structure_quality"]
    for c in TEXT_COLS:
        L.append(f"**{c}**")
        L.append("")
        for k, v in sq[c].items():
            L.append(f"- {k}: {v['count']:,} ({v['pct']}%)")
        L.append("")
    L.append(f"_{sq['note']}_")

    titles = {
        "malformed_text": "Malformed text indicators",
        "placeholders": "Placeholder / anonymisation artefacts",
        "privacy_indicators": "Privacy indicators (counts only)",
        "medical_risk_indicators": "Medical-risk indicators (approximate)",
        "emergency_related_questions": "Emergency-related questions (keyword flags, not triage)",
        "population_context": "Population context in questions",
    }
    for group, title in titles.items():
        L += ["", f"## {title}", ""] + _flag_table(report[group])

    L += ["", "## Most frequently mentioned medication names (rows)", ""]
    for c, v in report["medication_name_top_counts"].items():
        L.append(f"- **{c}**: " + ", ".join(f"{k} {n:,}" for k, n in v.items()))

    L += ["", "## Limitations", ""] + [f"- {x}" for x in report["limitations"]]
    L += ["", "Pattern definitions are recorded in the JSON report under `pattern_definitions`.", ""]
    return "\n".join(L)
