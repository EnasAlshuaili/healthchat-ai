"""TF-IDF retrieval-ranking baseline (step 4, D-05).

Ranks dataset questions by cosine similarity to a user question and returns
metadata only (source row, rank, score). It never loads or returns dataset
answers: answers are unverified and not approved for display (D-01), and a
similarity score is not evidence of medical correctness (D-14).

No confidence threshold is applied here. Threshold calibration happens in a
later step, on the validation set only (D-09).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from querymate import cleaning, config

RETRIEVAL_VERSION = "0.1.0"
PROCESSED_FILE = config.PROCESSED_DIR / "querymate_clean.parquet"

# Columns needed for retrieval. The `answer` column is deliberately excluded.
CORPUS_COLUMNS = ["source_row", "question", "retrieval_eligible", "display_allowed"]

DEFAULT_TOP_K = 5
MAX_TOP_K = 50

# Baseline vectorizer settings. Stop words are kept because negations and short
# function words ("not", "no", "after") can change medical meaning.
VECTORIZER_PARAMS = {
    "ngram_range": (1, 2),
    "lowercase": True,
    "min_df": 2,
    "sublinear_tf": False,
    "norm": "l2",
    "dtype": np.float32,
}


class CorpusError(RuntimeError):
    """The processed corpus is missing, malformed, or violates the display policy."""


@dataclass(frozen=True)
class RetrievalResult:
    """One ranked candidate. Contains no dataset text."""

    rank: int
    source_row: int
    score: float


def validate_query(query: object, max_chars: int = config.MAX_INPUT_CHARS) -> str:
    """Return the query with whitespace normalised, or raise.

    TypeError for non-strings; ValueError for empty/whitespace-only input (TC-02, TC-03)
    or input longer than `max_chars` (TC-12).
    """
    if not isinstance(query, str):
        raise TypeError("Question must be a string.")
    stripped = cleaning.normalize_whitespace(query)
    if not stripped:
        raise ValueError("Please enter a question.")
    if len(stripped) > max_chars:
        raise ValueError(f"Question is too long ({len(stripped)} characters); the limit is {max_chars}.")
    return stripped


def prepare_query(query: str) -> str:
    """Apply the same technical cleaning as the corpus (escapes, typography, whitespace, NFC, redaction)."""
    return cleaning.clean_text(query)


def load_corpus(path: Path = PROCESSED_FILE) -> pd.DataFrame:
    """Load retrieval-eligible questions from the processed dataset.

    Reads only CORPUS_COLUMNS (never `answer`). Raises CorpusError if the file is
    missing (TC-09), columns are absent, or any row is marked displayable.
    """
    path = Path(path)
    if not path.is_file():
        raise CorpusError(
            "Processed dataset not found. Run scripts/run_cleaning.py first."
        )
    try:
        df = pd.read_parquet(path, columns=CORPUS_COLUMNS)
    except (KeyError, ValueError) as exc:
        raise CorpusError(f"Processed dataset is missing required columns {CORPUS_COLUMNS}.") from exc
    if df["display_allowed"].any():
        raise CorpusError("Display policy violation: processed data marks rows as displayable (D-01).")
    if df["source_row"].duplicated().any():
        raise CorpusError("Processed dataset has duplicate source_row values.")
    eligible = df[df["retrieval_eligible"]].sort_values("source_row", kind="stable")
    return eligible[["source_row", "question"]].reset_index(drop=True)


class TfidfRetriever:
    """Word unigram+bigram TF-IDF over dataset questions, ranked by cosine similarity."""

    def __init__(self, **vectorizer_overrides):
        self.params = {**VECTORIZER_PARAMS, **vectorizer_overrides}
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        self._source_rows: np.ndarray | None = None

    @property
    def is_fitted(self) -> bool:
        return self._matrix is not None

    @property
    def corpus_size(self) -> int:
        return 0 if self._source_rows is None else len(self._source_rows)

    @property
    def vocabulary_size(self) -> int:
        return 0 if self._vectorizer is None else len(self._vectorizer.vocabulary_)

    def fit(self, questions, source_rows) -> "TfidfRetriever":
        questions = list(questions)
        source_rows = np.asarray(source_rows, dtype=np.int64)
        if len(questions) != len(source_rows):
            raise ValueError("questions and source_rows must have the same length.")
        if len(questions) == 0:
            raise ValueError("Cannot fit on an empty corpus.")
        if len(np.unique(source_rows)) != len(source_rows):
            raise ValueError("source_rows must be unique.")
        vectorizer = TfidfVectorizer(**self.params)
        self._matrix = vectorizer.fit_transform(questions).tocsr()
        self._vectorizer = vectorizer
        self._source_rows = source_rows
        return self

    @classmethod
    def from_corpus(cls, corpus: pd.DataFrame, **vectorizer_overrides) -> "TfidfRetriever":
        return cls(**vectorizer_overrides).fit(corpus["question"].tolist(), corpus["source_row"].to_numpy())

    def search(self, query: object, top_k: int = DEFAULT_TOP_K) -> list[RetrievalResult]:
        """Return up to `top_k` candidates with score > 0, highest score first.

        Ties are broken by ascending source_row, so results are deterministic.
        Returns an empty list when the query shares no indexed terms with the corpus.
        No relevance threshold is applied.
        """
        if not self.is_fitted:
            raise RuntimeError("Retriever is not fitted.")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= MAX_TOP_K:
            raise ValueError(f"top_k must be an integer between 1 and {MAX_TOP_K}.")
        text = prepare_query(validate_query(query))

        q = self._vectorizer.transform([text])
        if q.nnz == 0:
            return []
        # Rows are L2-normalised, so the dot product equals cosine similarity.
        scores = (self._matrix @ q.T).toarray().ravel()

        positive = np.flatnonzero(scores > 0)
        if positive.size == 0:
            return []
        if positive.size > top_k:
            # Keep every candidate tied with the k-th best score so tie-breaking stays exact.
            kth = np.partition(scores[positive], positive.size - top_k)[positive.size - top_k]
            positive = positive[scores[positive] >= kth]
        order = np.lexsort((self._source_rows[positive], -scores[positive]))[:top_k]
        chosen = positive[order]
        return [
            RetrievalResult(rank=i + 1, source_row=int(self._source_rows[idx]), score=round(float(scores[idx]), 6))
            for i, idx in enumerate(chosen)
        ]

    def fingerprint(self) -> dict:
        """Settings and corpus identity, for reproducibility records."""
        if not self.is_fitted:
            raise RuntimeError("Retriever is not fitted.")
        rows_hash = hashlib.sha256(self._source_rows.tobytes()).hexdigest()
        return {
            "retrieval_version": RETRIEVAL_VERSION,
            "vectorizer": {k: (np.dtype(v).name if k == "dtype" else v) for k, v in self.params.items()},
            "corpus_size": self.corpus_size,
            "vocabulary_size": self.vocabulary_size,
            "source_rows_sha256": rows_hash,
        }
