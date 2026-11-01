"""Tests for the TF-IDF retrieval-ranking baseline (step 4).

Synthetic corpora only, except the final module, which fits the real processed
corpus once. No threshold is tested here, and no test uses the test question set.
"""

import dataclasses

import numpy as np
import pandas as pd
import pytest

from querymate import config, retrieval
from querymate.retrieval import CorpusError, RetrievalResult, TfidfRetriever

CORPUS = {
    10: "What are the symptoms of diabetes in adults?",
    11: "How can I treat a migraine headache at home?",
    12: "Is high blood pressure dangerous during pregnancy?",
    13: "My blood test shows low iron and I feel tired.",
    14: "Pressure in my ears after a flight, what causes it?",
    15: "Can diabetes cause blurred vision and thirst?",
}


@pytest.fixture
def retriever():
    return TfidfRetriever(min_df=1).fit(list(CORPUS.values()), list(CORPUS.keys()))


# --- Ranking -----------------------------------------------------------------

def test_relevant_question_ranks_first(retriever):
    results = retriever.search("symptoms of diabetes", top_k=3)
    assert results[0].source_row == 10
    assert {r.source_row for r in results} >= {10, 15}


def test_scores_sorted_ranks_sequential_and_bounded(retriever):
    results = retriever.search("diabetes blood pressure", top_k=6)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
    assert [r.rank for r in results] == list(range(1, len(results) + 1))
    assert all(0 < s <= 1.0 + 1e-6 for s in scores)


def test_bigram_phrase_outranks_separate_words(retriever):
    # Row 12 contains the bigram "blood pressure"; rows 13 and 14 contain only one word each.
    results = retriever.search("blood pressure", top_k=3)
    assert results[0].source_row == 12


def test_identical_question_scores_one(retriever):
    results = retriever.search(CORPUS[11], top_k=1)
    assert results[0].source_row == 11
    assert results[0].score == pytest.approx(1.0, abs=1e-5)


def test_top_k_limits_results(retriever):
    assert len(retriever.search("diabetes", top_k=1)) == 1
    assert len(retriever.search("diabetes", top_k=50)) == 2  # only rows with score > 0


def test_case_and_whitespace_insensitive(retriever):
    a = retriever.search("SYMPTOMS   of\tDiabetes")
    b = retriever.search("symptoms of diabetes")
    assert a == b


# --- Input validation ----------------------------------------------------------

@pytest.mark.parametrize("bad", ["", "   ", "\n\t "])
def test_empty_or_whitespace_query_rejected(retriever, bad):
    with pytest.raises(ValueError, match="enter a question"):
        retriever.search(bad)


@pytest.mark.parametrize("bad", [None, 42, ["diabetes"], b"diabetes"])
def test_non_string_query_rejected(retriever, bad):
    with pytest.raises(TypeError):
        retriever.search(bad)


def test_too_long_query_rejected(retriever):
    with pytest.raises(ValueError, match="too long"):
        retriever.search("diabetes " * 200)


@pytest.mark.parametrize("bad", [0, -1, 51, 2.5, "5", True])
def test_invalid_top_k_rejected(retriever, bad):
    with pytest.raises(ValueError):
        retriever.search("diabetes", top_k=bad)


def test_unfitted_retriever_raises():
    with pytest.raises(RuntimeError):
        TfidfRetriever().search("diabetes")


def test_fit_validation():
    with pytest.raises(ValueError):
        TfidfRetriever().fit([], [])
    with pytest.raises(ValueError):
        TfidfRetriever().fit(["a b", "c d"], [1])
    with pytest.raises(ValueError):
        TfidfRetriever().fit(["a b", "c d"], [1, 1])


# --- Unknown / unrelated queries -------------------------------------------------

def test_unrelated_query_returns_no_candidates(retriever):
    assert retriever.search("quantum chromodynamics lattice simulation") == []


def test_single_character_tokens_only_returns_no_candidates(retriever):
    # The default token pattern ignores 1-character tokens, so nothing is indexed.
    assert retriever.search("? ! x") == []


def test_partial_overlap_returns_low_scores_not_a_threshold(retriever):
    # Unrelated question sharing only a common word still gets a score; no threshold
    # is applied at this stage, so callers must not treat any result as relevant.
    results = retriever.search("what is the capital of australia")
    assert results and all(r.score < 0.5 for r in results)


# --- Determinism -----------------------------------------------------------------

def test_reproducible_across_fits_and_calls():
    a = TfidfRetriever(min_df=1).fit(list(CORPUS.values()), list(CORPUS.keys()))
    b = TfidfRetriever(min_df=1).fit(list(CORPUS.values()), list(CORPUS.keys()))
    for q in ["diabetes", "blood pressure pregnancy", "migraine at home"]:
        assert a.search(q, top_k=5) == b.search(q, top_k=5) == a.search(q, top_k=5)
    assert a.fingerprint() == b.fingerprint()


def test_ties_broken_by_source_row_including_at_cutoff():
    docs = ["knee pain after running"] * 4 + ["shoulder pain"]
    rows = [40, 7, 23, 3, 99]
    r = TfidfRetriever(min_df=1).fit(docs, rows)
    results = r.search("knee pain after running", top_k=2)
    assert [x.source_row for x in results] == [3, 7]
    assert results[0].score == results[1].score


# --- No dataset text in results ------------------------------------------------------

def test_results_contain_metadata_only(retriever):
    fields = {f.name for f in dataclasses.fields(RetrievalResult)}
    assert fields == {"rank", "source_row", "score"}
    for r in retriever.search("diabetes"):
        assert isinstance(r.source_row, int) and isinstance(r.score, float)


# --- Corpus loading ----------------------------------------------------------------

def _write_processed(path, display_allowed=False, eligible=(True, True, False), dup=False):
    rows = [5, 6, 6 if dup else 7]
    pd.DataFrame({
        "source_row": rows,
        "question": ["first question about asthma", "second question about asthma", "hello"],
        "retrieval_eligible": list(eligible),
        "display_allowed": [display_allowed, False, False],
    }).to_parquet(path, index=False)
    return path


def test_load_corpus_filters_eligible_and_skips_answers(tmp_path):
    corpus = retrieval.load_corpus(_write_processed(tmp_path / "p.parquet"))
    # Works without an `answer` column at all, proving answers are never needed or read.
    assert list(corpus.columns) == ["source_row", "question"]
    assert corpus["source_row"].tolist() == [5, 6]


def test_load_corpus_refuses_displayable_rows(tmp_path):
    with pytest.raises(CorpusError, match="Display policy"):
        retrieval.load_corpus(_write_processed(tmp_path / "p.parquet", display_allowed=True))


def test_load_corpus_rejects_duplicate_source_rows(tmp_path):
    with pytest.raises(CorpusError, match="duplicate"):
        retrieval.load_corpus(_write_processed(tmp_path / "p.parquet", dup=True))


def test_load_corpus_missing_file(tmp_path):
    with pytest.raises(CorpusError, match="not found"):
        retrieval.load_corpus(tmp_path / "missing.parquet")


def test_load_corpus_missing_columns(tmp_path):
    path = tmp_path / "p.parquet"
    pd.DataFrame({"source_row": [1], "question": ["x y"]}).to_parquet(path, index=False)
    with pytest.raises(CorpusError, match="missing required columns"):
        retrieval.load_corpus(path)


# --- Real processed corpus (fitted once) ---------------------------------------------

needs_processed = pytest.mark.skipif(
    not retrieval.PROCESSED_FILE.exists(), reason="processed dataset not present")


@pytest.fixture(scope="module")
def real_retriever():
    corpus = retrieval.load_corpus()
    return corpus, TfidfRetriever.from_corpus(corpus)


@needs_processed
def test_real_corpus_is_eligible_rows_only(real_retriever):
    corpus, r = real_retriever
    full = pd.read_parquet(retrieval.PROCESSED_FILE, columns=["retrieval_eligible", "display_allowed"])
    assert r.corpus_size == len(corpus) == int(full["retrieval_eligible"].sum())
    assert not full["display_allowed"].any()
    assert corpus["source_row"].is_monotonic_increasing


@needs_processed
def test_real_search_is_deterministic_and_ranked(real_retriever):
    corpus, r = real_retriever
    eligible_rows = set(corpus["source_row"])
    # Validation-set question only (never the test set).
    q = "What are common signs of dehydration in adults?"
    a, b = r.search(q, top_k=10), r.search(q, top_k=10)
    assert a == b and len(a) == 10
    assert [x.score for x in a] == sorted((x.score for x in a), reverse=True)
    assert all(x.source_row in eligible_rows for x in a)


@needs_processed
def test_real_exact_corpus_question_retrieves_itself(real_retriever):
    corpus, r = real_retriever
    short = corpus[corpus["question"].str.len() <= config.MAX_INPUT_CHARS]
    for i in np.linspace(0, len(short) - 1, 5).astype(int):
        row = short.iloc[i]
        top = r.search(row["question"], top_k=1)[0]
        assert top.source_row == row["source_row"]
        assert top.score == pytest.approx(1.0, abs=1e-4)
