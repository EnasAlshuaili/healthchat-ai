"""Curated Topic Matcher, first version (D-15).

Ranks the curated educational topics by TF-IDF cosine similarity to a user
question and returns topic IDs and scores only, or NONE when the configured
abstention rule is not met.

What a match means, and what it does not:
- A match decides topical relevance only. It is not evidence of medical
  correctness or safety, and it never gives permission to display content
  (D-01, D-14, D-15(d)).
- Safety and scope come first. `match_after_precheck` scores a question only when
  a pre-check result says PROCEED; every other route is returned unchanged with
  topic NONE, so a topic match can never override emergency, crisis, diagnosis,
  dosage, out-of-scope, invalid-input, or fallback handling. The pre-check is the
  prototype Safety & Scope Router (`querymate.safety`); it is not wired to any
  user-facing flow yet.
- Topic examples are AI-assisted and `pending_owner_review`. By default only
  `owner_approved` examples are indexed (currently none, so the matcher uses topic
  names and descriptions). `include_pending_examples=True` is an explicit,
  experiment-only switch; results produced with it are provisional and carry the
  D-15 contamination caveat. This module never changes an example's status.
- Exclusion text is deliberately not indexed: its words ("dose", "diagnose") would
  attract exactly the requests that must be routed elsewhere.

No dataset text or answers are read. No external service is used (D-06).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from querymate import curated, retrieval
from querymate.safety import PreCheckResult, Route  # noqa: F401 - single definition, re-exported

MATCHER_VERSION = "0.1.0"
NO_TOPIC = curated.NO_TOPIC
TOP_CANDIDATES = 3

# D-15(c): B1 = word TF-IDF over the catalogue, B2 = character n-gram TF-IDF.
# Stop words are kept, as in the retrieval baseline (negations can matter).
METHODS = {
    "word": {"analyzer": "word", "ngram_range": (1, 2), "lowercase": True, "min_df": 1,
             "norm": "l2", "dtype": np.float32},
    "char": {"analyzer": "char_wb", "ngram_range": (3, 5), "lowercase": True, "min_df": 1,
             "norm": "l2", "dtype": np.float32},
}
OWNER_APPROVED = "owner_approved"
PENDING = "pending_owner_review"


@dataclass(frozen=True)
class AbstentionRule:
    """Return NONE unless top-1 score >= min_score and (top-1 - top-2) >= min_margin.

    There is no default threshold. Any value chosen on Validation is provisional.
    """

    min_score: float
    min_margin: float = 0.0

    def __post_init__(self):
        for name in ("min_score", "min_margin"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0.0 <= v <= 1.0:
                raise ValueError(f"{name} must be a number between 0 and 1.")


@dataclass(frozen=True)
class TopicScore:
    topic_id: str
    score: float


@dataclass(frozen=True)
class TopicMatch:
    """Topic IDs and scores only; no question, topic, or example text."""

    topic_id: str                 # a TOP-### ID or NONE
    score: float                  # top-1 score (0.0 when nothing overlaps)
    margin: float                 # top-1 minus top-2 score
    candidates: tuple[TopicScore, ...]
    abstain_reason: str | None    # None, "no_overlap", "below_min_score", "below_min_margin"
    uses_pending_examples: bool   # True = provisional experiment result (D-15)


@dataclass(frozen=True)
class GatedResult:
    route: Route
    match: TopicMatch | None  # None whenever the route is not PROCEED

    @property
    def topic_id(self) -> str:
        return self.match.topic_id if self.match else NO_TOPIC


class TopicMatcher:
    """TF-IDF over topic names, descriptions, and eligible examples; topic score = best text."""

    def __init__(self, method: str, rule: AbstentionRule):
        if method not in METHODS:
            raise ValueError(f"method must be one of {sorted(METHODS)}.")
        if not isinstance(rule, AbstentionRule):
            raise TypeError("rule must be an AbstentionRule.")
        self.method, self.rule = method, rule
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        self._doc_topics: np.ndarray | None = None
        self._topic_ids: list[str] = []
        self._counts: dict = {}
        self.uses_pending_examples = False

    @property
    def is_fitted(self) -> bool:
        return self._matrix is not None

    def fit(self, topics: pd.DataFrame, examples: pd.DataFrame | None = None,
            include_pending_examples: bool = False) -> "TopicMatcher":
        """Index each topic's name and description, plus its eligible examples.

        Eligible examples: `owner_approved`, plus `pending_owner_review` only when
        `include_pending_examples` is True. The input frames are not modified.
        """
        if topics.empty or topics["topic_id"].duplicated().any():
            raise ValueError("topics must be non-empty with unique topic_id values.")
        ids = list(topics["topic_id"])
        docs, owners = [], []
        for t in topics.itertuples(index=False):
            docs += [t.topic_name, t.description]
            owners += [t.topic_id, t.topic_id]
        statuses = {OWNER_APPROVED} | ({PENDING} if include_pending_examples else set())
        n_examples = 0
        if examples is not None and len(examples):
            if bad := set(examples["topic_id"]) - set(ids):
                raise ValueError(f"examples reference unknown topics {sorted(bad)}.")
            eligible = examples[examples["review_status"].isin(statuses)]
            docs += list(eligible["example_question"])
            owners += list(eligible["topic_id"])
            n_examples = len(eligible)
        vectorizer = TfidfVectorizer(**METHODS[self.method])
        self._matrix = vectorizer.fit_transform(docs).tocsr()
        self._vectorizer = vectorizer
        self._doc_topics = np.array([ids.index(o) for o in owners])
        self._topic_ids = ids
        self.uses_pending_examples = bool(include_pending_examples and n_examples)
        self._counts = {"topics": len(ids), "topic_texts": 2 * len(ids), "examples_indexed": n_examples,
                        "example_statuses_indexed": sorted(statuses)}
        return self

    def rank_for_evaluation(self, query: object) -> TopicMatch:
        """Score a question WITHOUT any safety/scope gate.

        For offline evaluation only (for example, reporting policy-routed validation
        questions as risk indicators). Anything serving users must use
        `match_after_precheck`.
        """
        if not self.is_fitted:
            raise RuntimeError("Topic matcher is not fitted.")
        text = retrieval.prepare_query(retrieval.validate_query(query))
        q = self._vectorizer.transform([text])
        doc_scores = (self._matrix @ q.T).toarray().ravel() if q.nnz else np.zeros(self._matrix.shape[0])
        topic_scores = np.zeros(len(self._topic_ids))
        np.maximum.at(topic_scores, self._doc_topics, doc_scores)
        # Highest score first; ties broken by topic_id so results are deterministic.
        order = sorted(range(len(self._topic_ids)), key=lambda i: (-round(topic_scores[i], 6), self._topic_ids[i]))
        ranked = tuple(TopicScore(self._topic_ids[i], round(float(topic_scores[i]), 6)) for i in order)
        top1 = ranked[0].score
        margin = round(top1 - ranked[1].score, 6) if len(ranked) > 1 else top1
        if top1 <= 0.0:
            reason = "no_overlap"
        elif top1 < self.rule.min_score:
            reason = "below_min_score"
        elif margin < self.rule.min_margin:
            reason = "below_min_margin"
        else:
            reason = None
        return TopicMatch(topic_id=ranked[0].topic_id if reason is None else NO_TOPIC, score=top1,
                          margin=margin, candidates=ranked[:TOP_CANDIDATES], abstain_reason=reason,
                          uses_pending_examples=self.uses_pending_examples)

    def match_after_precheck(self, query: object, precheck: PreCheckResult) -> GatedResult:
        """Match a question only after a safety/scope pre-check decided PROCEED.

        Any other route is returned unchanged with topic NONE, and the question is not
        scored at all, so a topic match can never make such a request "safe".
        """
        if not isinstance(precheck, PreCheckResult) or not isinstance(precheck.route, Route):
            raise TypeError("A PreCheckResult from the safety/scope pre-check is required before matching.")
        if precheck.route is not Route.PROCEED:
            return GatedResult(route=precheck.route, match=None)
        return GatedResult(route=Route.PROCEED, match=self.rank_for_evaluation(query))

    def fingerprint(self) -> dict:
        if not self.is_fitted:
            raise RuntimeError("Topic matcher is not fitted.")
        params = {k: (np.dtype(v).name if k == "dtype" else v) for k, v in METHODS[self.method].items()}
        return {"matcher_version": MATCHER_VERSION, "method": self.method, "vectorizer": params,
                "rule": {"min_score": self.rule.min_score, "min_margin": self.rule.min_margin},
                "vocabulary_size": len(self._vectorizer.vocabulary_),
                "uses_pending_examples": self.uses_pending_examples, **self._counts}


def build_from_curated(method: str, rule: AbstentionRule, include_pending_examples: bool = False) -> TopicMatcher:
    """Fit on curated/topics.csv and curated/topic_examples.csv after full validation."""
    topics = curated.load_topics()
    examples = curated.load_topic_examples()
    problems = curated.validate_topics(topics) + curated.validate_topic_examples(examples, topics)
    if problems:
        raise ValueError(f"Curated files failed validation: {problems}")
    return TopicMatcher(method, rule).fit(topics, examples, include_pending_examples=include_pending_examples)
