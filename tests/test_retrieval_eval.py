"""Tests for the validation-only retrieval analysis helpers."""

import pandas as pd
import pytest

from querymate import config, retrieval_eval as rev
from querymate.retrieval import TfidfRetriever


@pytest.fixture
def tiny():
    corpus = {1: "symptoms of diabetes in adults", 2: "migraine headache treatment at home",
              3: "high blood pressure in pregnancy", 4: "low iron and tiredness"}
    r = TfidfRetriever(min_df=1).fit(list(corpus.values()), list(corpus.keys()))
    q = pd.DataFrame({
        "question_id": ["V001", "V002", "V003", "V004"],
        "question": ["What are diabetes symptoms?", "How is a migraine headache treated?",
                     "Is it bad?", "zzz qqq"],
        "category": ["general_education", "paraphrase", "ambiguous", "out_of_scope"],
        "expected_behavior": ["educational_answer_or_fallback", "educational_answer_or_fallback",
                              "clarify_or_fallback", "out_of_scope_fallback"],
        "rationale": ["x", "Paraphrase of V001", "x", "x"],
    })
    return r, q


def test_refuses_test_set_and_non_validation_ids(tmp_path):
    with pytest.raises(ValueError, match="validation"):
        rev.load_validation(config.EVAL_DIR / "test_questions.csv")
    bad = tmp_path / "validation_questions.csv"
    pd.DataFrame({"question_id": ["T001"], "question": ["x"], "category": ["a"],
                  "expected_behavior": ["b"], "rationale": ["c"]}).to_csv(bad, index=False)
    with pytest.raises(ValueError, match="non-validation"):
        rev.load_validation(bad)


def test_real_validation_file_loads_40_rows():
    assert len(rev.load_validation()) == 40


def test_proxy_groups():
    assert rev.proxy_group("paraphrase") == "answerable_proxy"
    assert rev.proxy_group("out_of_scope") == "abstain_proxy"
    assert rev.proxy_group("emergency") == "policy_routed"


def test_evaluate_outputs_ids_and_scores_only(tiny):
    r, q = tiny
    res = rev.evaluate(r, q)
    assert "question" not in res.columns and "answer" not in res.columns
    assert res.loc[0, "top1_source_row"] == 1
    no_hit = res.set_index("question_id").loc["V004"]
    assert no_hit["n_candidates"] == 0 and no_hit["top1_score"] == 0.0
    assert no_hit["query_vocab_coverage"] == 0.0
    blob = res.to_csv()
    for text in q["question"]:
        assert text not in blob


def test_signal_separation_auc_and_sweep():
    df = pd.DataFrame({
        "question_id": [f"V{i:03d}" for i in range(1, 7)],
        "proxy_group": ["answerable_proxy"] * 2 + ["abstain_proxy"] * 2 + ["policy_routed"] * 2,
        "top1_score": [0.9, 0.8, 0.2, 0.1, 0.5, 0.95],
    })
    s = rev.signal_separation(df, "top1_score")
    assert s["auc_answerable_vs_abstain"] == 1.0
    row = next(x for x in s["sweep"] if x["accept_if_at_least"] == 0.8)
    assert row == {"accept_if_at_least": 0.8, "answerable_proxy_accepted": "2/2",
                   "abstain_proxy_accepted": "0/2", "policy_routed_accepted": "1/2"}
    df["top1_score"] = [0.1, 0.2, 0.8, 0.9, 0.5, 0.5]
    assert rev.signal_separation(df, "top1_score")["auc_answerable_vs_abstain"] == 0.0


def test_paraphrase_consistency_and_hubs(tiny):
    r, q = tiny
    res = rev.evaluate(r, q)
    pc = rev.paraphrase_consistency(res, q)
    assert pc == [{"paraphrase": "V002", "source": "V001",
                   "same_top1": bool(res.loc[1, "top1_source_row"] == res.loc[0, "top1_source_row"]),
                   "top_k_overlap": pc[0]["top_k_overlap"]}]
    assert rev.hub_rows(res)["questions"] == 4


def test_review_sheet_has_blank_review_fields_and_no_text(tiny):
    r, q = tiny
    sheet = rev.review_sheet(rev.evaluate(r, q))
    assert list(sheet.columns[-4:]) == ["retrieval_relevance", "reviewer", "review_date", "notes"]
    assert (sheet["retrieval_relevance"] == "").all()
    assert "question" not in sheet.columns
