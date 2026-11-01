"""Response pipeline (docs/API_CONTRACT.md): router first, then curated knowledge after PROCEED.

Templates and example payloads are checked against the contract document itself,
not against a copy of the pipeline's logic.
"""

import ast
import dataclasses
import json
import logging
import re
import subprocess
import sys

import pytest

from querymate import config, knowledge, pipeline, safety
from querymate.safety import Route, RouteDecision
from querymate.ui.content import DISCLAIMER

CONTRACT = (config.PROJECT_ROOT / "docs" / "API_CONTRACT.md").read_text(encoding="utf-8")
# Historical record, not rewritten: it keeps the old product name (D-22), the only permitted difference.
REVIEW = (config.PROJECT_ROOT / "docs" / "STEP3_DECISION_REVIEW.md").read_text(encoding="utf-8").replace(
    "QueryMate", "HealthChat AI"
)
MARKER = "ZZQ-MARKER-7f3a"

# Real router inputs for each route (the same style as tests/test_safety.py).
ROUTE_EXAMPLES = {
    Route.PROCEED: "What is LDL cholesterol?",
    Route.CRISIS: "I want to kill myself, what is cholesterol",
    Route.EMERGENCY: "I have chest pain, what is LDL cholesterol?",
    Route.DOSAGE: "What dose of statin lowers LDL cholesterol?",
    Route.DIAGNOSIS: "Do I have high cholesterol?",
    Route.SAFE_FALLBACK: "Guarantee that LDL cholesterol is bad",
    Route.OUT_OF_SCOPE: "My dog has high cholesterol",
    Route.INVALID_INPUT: "   ",
}
EXPECTED_KEY = {
    Route.PROCEED: "safe_fallback",  # no curated entry for this question (D-02)
    Route.CRISIS: "crisis",
    Route.EMERGENCY: "emergency",
    Route.DOSAGE: "decline_dosage",
    Route.DIAGNOSIS: "decline_diagnosis",
    Route.SAFE_FALLBACK: "safe_fallback",
    Route.OUT_OF_SCOPE: "out_of_scope",
    Route.INVALID_INPUT: "invalid_input:empty",
}
CONTRACT_KEYS = {  # contract template headings -> pipeline template keys
    "invalid_input:empty question": "invalid_input:empty",
    "invalid_input:over-length question": "invalid_input:too_long",
}


def contract_templates() -> dict[str, tuple[str, list[str]]]:
    section = CONTRACT.split("### Reply templates")[1].split("Caveats recorded")[0]
    found = {}
    for m in re.finditer(r'\*\*`(\w+)`(?:, ([\w -]+))?\*\*: title "([^"]+)"\n\n((?:\d+\. .*\n)+)', section):
        key = m.group(1) + (f":{m.group(2)}" if m.group(2) else "")
        paragraphs = [re.sub(r"^\d+\. ", "", line) for line in m.group(4).strip().split("\n")]
        found[CONTRACT_KEYS.get(key, key)] = (m.group(3), paragraphs)
    return found


def assert_contract_invariants(result: pipeline.ChatResult):
    body = result.to_dict("rid")
    assert body["api_version"] == "0.3"
    assert body["is_mock"] is (body["kind"] == "mock_answer")
    curated = body["kind"] == "curated_answer"
    assert bool(body["sources"]) is curated
    assert (body["review_status"] == "owner_reviewed") is curated and (body["review_status"] is None) is not curated
    assert (body["versions"]["knowledge"] == "0.1.0") is curated
    assert (body["versions"]["knowledge"] is None) is not curated
    expected_source = {"curated_answer": "curated_owner_reviewed", "mock_answer": "mock_placeholder",
                       "invalid_input": "input_check"}
    assert body["content_source"] == expected_source.get(body["kind"], "safety_template")
    assert body["versions"]["matcher"] is None
    assert body["versions"]["content"] == "templates-0.1"
    assert body["versions"]["router"] in ("0.1.1", None)
    assert body["abstained"] is False and body["abstain_reason"] is None
    assert body["disclaimer"] == DISCLAIMER
    assert 1 <= len(body["message"]["paragraphs"]) <= 5


def assert_fail_closed(result: pipeline.ChatResult):
    assert result.kind == "safe_fallback"
    assert (result.title, result.paragraphs) == (pipeline.TEMPLATES["safe_fallback"].title,
                                                pipeline.TEMPLATES["safe_fallback"].paragraphs)
    assert result.router_version is None
    assert_contract_invariants(result)


# --- 16. Templates match the contract exactly ----------------------------------------------

def test_every_template_matches_the_contract_exactly():
    expected = contract_templates()
    assert set(expected) == set(pipeline.TEMPLATES)
    for key, template in pipeline.TEMPLATES.items():
        assert (template.title, list(template.paragraphs)) == expected[key], key


def test_disclaimer_is_the_06_wording():
    ui_doc = (config.PROJECT_ROOT / "docs" / "06_UI_UX_Design.md").read_text(encoding="utf-8")
    assert DISCLAIMER in ui_doc.replace("\u201c", "").replace("\u201d", "")


def test_mock_and_input_templates_match_the_current_api():
    from querymate.api import replies
    assert pipeline.TEMPLATES["mock_answer"].paragraphs == tuple(replies._MOCK_ANSWER.paragraphs)
    assert pipeline.TEMPLATES["invalid_input:empty"].title == replies._EMPTY.title
    assert pipeline.TEMPLATES["invalid_input:too_long"].paragraphs == tuple(replies._TOO_LONG.paragraphs)


def documented_examples(doc: str) -> list[dict]:
    examples = []
    for block in re.findall(r"```json\n(.*?)```", doc, re.S):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue  # the contract's diagnostics fragment
        if "kind" in data:
            examples.append(data)
    assert examples
    return examples


def result_for_example(example: dict, monkeypatch) -> pipeline.ChatResult:
    inputs = {"curated_answer": "Why is staying hydrated important?", "emergency": ROUTE_EXAMPLES[Route.EMERGENCY],
              "crisis": ROUTE_EXAMPLES[Route.CRISIS], "decline_dosage": ROUTE_EXAMPLES[Route.DOSAGE]}
    kind = example["kind"]
    if kind == "invalid_input":
        return pipeline.respond("   " if example["message"]["title"].startswith("Please enter") else "a" * 1001)
    if kind == "safe_fallback":  # the documented router-internal-error example
        with monkeypatch.context() as m:
            m.setattr(safety, "_route", lambda q: (_ for _ in ()).throw(RuntimeError("boom")))
            return pipeline.respond("What is LDL cholesterol?")
    return pipeline.respond(inputs[kind])


def test_contract_example_payloads_are_reproduced_exactly(monkeypatch):
    for example in documented_examples(CONTRACT):
        assert result_for_example(example, monkeypatch).to_dict(example["request_id"]) == example, example["kind"]


def test_historical_v02_review_examples_still_match_the_served_replies(monkeypatch):
    # STEP3_DECISION_REVIEW.md is the historical v0.2 record and is not rewritten. Every field that
    # v0.2 defined must still be served as recorded; only the version number and the fields v0.3
    # added differ. The recorded mock example stands as the approved template text, no longer served.
    for example in documented_examples(REVIEW):
        if example["kind"] == "mock_answer":
            template = pipeline.TEMPLATES["mock_answer"]
            assert example["message"] == {"title": template.title, "paragraphs": list(template.paragraphs)}
            assert example["is_mock"] is True and example["content_source"] == "mock_placeholder"
            continue
        body = result_for_example(example, monkeypatch).to_dict(example["request_id"])
        assert body["api_version"] == "0.3" and example["api_version"] == "0.2"
        assert (body["sources"], body["review_status"]) == ([], None)
        assert body["versions"].pop("knowledge") is None
        kept = {k: v for k, v in body.items() if k not in ("api_version", "sources", "review_status")}
        assert kept == {k: v for k, v in example.items() if k != "api_version"}, example["kind"]


# --- 1, 2. Route mapping and emergency/crisis wording --------------------------------------

@pytest.mark.parametrize("route", list(Route), ids=lambda r: r.name)
def test_every_router_route_maps_to_its_approved_template(route):
    question = ROUTE_EXAMPLES[route]
    assert safety.route(question).route is route  # the example really takes this route
    result = pipeline.respond(question)
    template = pipeline.TEMPLATES[EXPECTED_KEY[route]]
    assert (result.kind, result.title, result.paragraphs) == (template.kind, template.title, template.paragraphs)
    assert result.router_version == "0.1.1"
    assert_contract_invariants(result)


def test_all_eight_routes_are_covered():
    assert set(ROUTE_EXAMPLES) == set(Route) and len(Route) == 8


def test_emergency_and_crisis_wording_and_order():
    emergency = pipeline.respond(ROUTE_EXAMPLES[Route.EMERGENCY])
    crisis = pipeline.respond(ROUTE_EXAMPLES[Route.CRISIS])
    approved_emergency = contract_templates()["emergency"][1]
    assert list(emergency.paragraphs) == approved_emergency
    assert list(crisis.paragraphs[:2]) == approved_emergency  # emergency first, unchanged
    assert len(crisis.paragraphs) == 3
    assert crisis.paragraphs[2].startswith("If you are thinking about harming yourself")
    for result in (emergency, crisis):  # guidance only: no follow-up questions
        assert not any(p.rstrip().endswith("?") for p in result.paragraphs)


# --- 3, 4, 5, 6. Input validation and INVALID_INPUT selection ------------------------------

@pytest.mark.parametrize("question", ["", " ", "\n\t  \r\n"], ids=["empty", "space", "whitespace"])
def test_empty_and_whitespace_input(question):
    result = pipeline.respond(question)
    assert (result.kind, result.title) == ("invalid_input", "Please enter a question.")
    assert result.router_version == "0.1.1"


@pytest.mark.parametrize("question", [None, 42, 3.5, b"bytes", ["What is fibre?"], {"question": "x"}],
                         ids=["none", "int", "float", "bytes", "list", "dict"])
def test_non_text_input_gets_the_empty_reply(question):
    assert safety.route(question).reason_codes == ("input:not_text",)
    result = pipeline.respond(question)
    assert (result.kind, result.title) == ("invalid_input", "Please enter a question.")


def test_input_at_limit_proceeds_and_over_limit_is_too_long():
    assert pipeline.respond("a" * 990 + " fibre?").kind != "invalid_input"
    at_limit = "What is fibre? " + "a" * (config.MAX_INPUT_CHARS - 15)
    assert len(at_limit) == config.MAX_INPUT_CHARS and pipeline.respond(at_limit).kind == "safe_fallback"
    assert pipeline.respond(at_limit).router_version == "0.1.1"  # a router decision, not a failure
    result = pipeline.respond(at_limit + "a")
    assert (result.kind, result.title) == ("invalid_input", "Your question is too long.")
    assert pipeline.EMERGENCY_LINE in result.paragraphs


def test_empty_and_too_long_replies_differ():
    empty, long = pipeline.respond(""), pipeline.respond("a" * 1001)
    assert empty.kind == long.kind == "invalid_input"
    assert (empty.title, empty.paragraphs) != (long.title, long.paragraphs)


@pytest.mark.parametrize("prefix, kind", [
    ("I want to kill myself. ", "crisis"),
    ("I took a whole bottle of sleeping pills. ", "crisis"),
    ("I have chest pain and can't breathe. ", "emergency"),
], ids=["crisis", "overdose", "emergency"])
def test_over_length_input_with_urgent_signal_gets_urgent_reply(prefix, kind):
    question = prefix + "word " * 400
    assert len(question) > config.MAX_INPUT_CHARS
    decision = safety.route(question)
    assert "input:too_long" in decision.reason_codes  # length was exceeded...
    assert pipeline.respond(question).kind == kind     # ...but urgent guidance comes first (D-17 P4)


def test_urgent_signal_beyond_the_scan_limit_is_not_seen():
    # Documented router limitation (SCAN_LIMIT_CHARS = 20,000): the pipeline does not add its own scan.
    question = "a" * safety.SCAN_LIMIT_CHARS + " I have chest pain"
    assert pipeline.respond(question).title == "Your question is too long."


def test_too_long_with_other_risk_codes_still_selects_too_long_reply():
    question = "What dose should I take? " + "word " * 300
    decision = safety.route(question)
    assert decision.route is Route.INVALID_INPUT and len(decision.reason_codes) > 1
    assert pipeline.respond(question).title == "Your question is too long."


@pytest.mark.parametrize("codes", [("scope:no_health_vocabulary",), ("framing:unclear",),
                                   ("dosage:dose_words",)], ids=["scope", "framing", "dosage"])
def test_invalid_input_without_input_reason_code_fails_closed(codes, monkeypatch, caplog):
    assert set(codes) <= safety.REASON_CODES  # known codes, but not input codes
    monkeypatch.setattr(safety, "route", lambda q: RouteDecision(Route.INVALID_INPUT, codes))
    with caplog.at_level(logging.ERROR, logger="querymate.pipeline"):
        assert_fail_closed(pipeline.respond("What is fibre?"))
    assert "failed closed" in caplog.text


# --- 7, 8, 14. Order, no matcher, no dataset ------------------------------------------------

def test_router_runs_first_and_receives_the_question_unchanged(monkeypatch):
    calls = []
    real_route = safety.route
    question = "  What is LDL cholesterol?  "

    def spy_route(q):
        calls.append(("router", q))
        return real_route(q)

    class SpyTemplates(dict):
        def __getitem__(self, key):
            calls.append(("template", key))
            return super().__getitem__(key)

    monkeypatch.setattr(safety, "route", spy_route)
    monkeypatch.setattr(pipeline, "TEMPLATES", SpyTemplates(pipeline.TEMPLATES))
    pipeline.respond(question)
    assert calls == [("router", question), ("template", "safe_fallback")]
    assert calls[0][1] is question


def test_retrieval_runs_after_the_router_and_receives_the_question_unchanged(monkeypatch):
    calls = []
    real_route, real_retrieve = safety.route, knowledge.retrieve
    question = "  Why is staying hydrated important?  "
    monkeypatch.setattr(safety, "route", lambda q: calls.append(("router", q)) or real_route(q))
    monkeypatch.setattr(knowledge, "retrieve", lambda q: calls.append(("retrieve", q)) or real_retrieve(q))
    assert pipeline.respond(question).kind == "curated_answer"
    assert calls == [("router", question), ("retrieve", question)]
    assert calls[1][1] is question


def test_matcher_retrieval_and_dataset_are_never_used(monkeypatch):
    import pandas as pd

    from querymate import curated, retrieval, topic_matcher

    def forbidden(*_a, **_k):
        raise AssertionError("must not be called in Phase A")

    for owner, name in [(topic_matcher.TopicMatcher, "match_after_precheck"),
                        (topic_matcher.TopicMatcher, "rank_for_evaluation"),
                        (topic_matcher.TopicMatcher, "fit"), (topic_matcher, "build_from_curated"),
                        (retrieval.TfidfRetriever, "search"), (retrieval, "load_corpus"),
                        (curated, "load_topics"), (curated, "load_topic_examples"),
                        (pd, "read_csv"), (pd, "read_parquet")]:
        monkeypatch.setattr(owner, name, forbidden)
    for question in list(ROUTE_EXAMPLES.values()) + ["a" * 1001, None]:
        assert pipeline.respond(question).router_version == "0.1.1"  # no fail-closed: nothing was called


_OPENED: list[str] = []
_WATCH = {"on": False}


def _audit(event, args):
    if _WATCH["on"] and event == "open" and args and isinstance(args[0], (str, bytes)):
        _OPENED.append(str(args[0]))


sys.addaudithook(_audit)


def test_no_files_are_opened_while_answering():
    _OPENED.clear()
    _WATCH["on"] = True
    try:
        for question in list(ROUTE_EXAMPLES.values()) + ["a" * 1001, None]:
            pipeline.respond(question)
    finally:
        _WATCH["on"] = False
    assert _OPENED == []  # no dataset, index, curated, or other file is read


def test_pipeline_source_imports_only_router_and_static_copy():
    tree = ast.parse((config.PROJECT_ROOT / "src" / "querymate" / "pipeline.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.update(f"{node.module}.{a.name}" for a in node.names)
    assert imported == {"__future__.annotations", "logging", "dataclasses.dataclass", "typing.Literal",
                        "querymate.knowledge", "querymate.safety", "querymate.ui.content.DISCLAIMER"}


def test_importing_pipeline_loads_no_matcher_retrieval_or_curated_modules():
    code = ("import sys; sys.path.insert(0, 'src'); import querymate.pipeline; "
            "print(sorted(m for m in sys.modules if m in {'querymate.topic_matcher', 'querymate.retrieval', "
            "'querymate.curated', 'querymate.retrieval_eval', 'querymate.topic_eval', 'querymate.safety_eval', "
            "'querymate.api', 'fastapi'} or m.split('.')[0] == 'sklearn'))")
    out = subprocess.run([sys.executable, "-c", code], cwd=config.PROJECT_ROOT,
                         capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"


# --- 9, 10, 11. Fail closed -------------------------------------------------------------------

def test_router_exception_fails_closed_without_details(monkeypatch, caplog):
    def boom(_q):
        raise RuntimeError(f"secret {MARKER} at C:/internal/path.py")
    monkeypatch.setattr(safety, "route", boom)
    with caplog.at_level(logging.ERROR, logger="querymate.pipeline"):
        result = pipeline.respond(f"What is {MARKER}?")
    assert_fail_closed(result)
    text = json.dumps(result.to_dict("rid"))
    assert MARKER not in text and "RuntimeError" not in text and "path" not in text
    assert "router raised (RuntimeError)" in caplog.text and MARKER not in caplog.text


def test_router_internal_error_fallback_has_router_null(monkeypatch, caplog):
    monkeypatch.setattr(safety, "_route", lambda q: (_ for _ in ()).throw(ValueError("x")))
    assert safety.route("What is fibre?").reason_codes == ("router:error",)
    with caplog.at_level(logging.ERROR, logger="querymate.pipeline"):
        assert_fail_closed(pipeline.respond("What is fibre?"))
    assert "router internal error" in caplog.text


@pytest.mark.parametrize("decision", [
    None,
    "proceed",
    {"route": "proceed", "reason_codes": ("scope:health_vocabulary_no_risk_rule",)},
    RouteDecision("proceed", ("scope:health_vocabulary_no_risk_rule",)),     # route not an enum
    RouteDecision(Route.PROCEED, ("made:up",)),                              # unknown reason code
    RouteDecision(Route.PROCEED, ("scope:health_vocabulary_no_risk_rule", f"{MARKER}")),
    RouteDecision(Route.PROCEED, ()),                                       # no reason codes
    RouteDecision(Route.PROCEED, ["scope:health_vocabulary_no_risk_rule"]),  # not a tuple
    RouteDecision(Route.PROCEED, ("scope:health_vocabulary_no_risk_rule",), router_version="9.9.9"),
], ids=["none", "string", "dict", "string_route", "unknown_code", "marker_code", "no_codes", "list_codes",
        "unapproved_version"])
def test_invalid_router_decisions_fail_closed(decision, monkeypatch):
    monkeypatch.setattr(safety, "route", lambda q: decision)
    result = pipeline.respond("What is fibre?")
    assert_fail_closed(result)
    assert MARKER not in json.dumps(result.to_dict("rid"))


@pytest.mark.parametrize("attr, value", [("ROUTER_VERSION", "0.2.0"), ("MAX_INPUT_CHARS", 500),
                                         ("SCAN_LIMIT_CHARS", 10_000)])
def test_unapproved_router_build_fails_closed(attr, value, monkeypatch):
    monkeypatch.setattr(safety, attr, value)
    assert_fail_closed(pipeline.respond("What is LDL cholesterol?"))


def test_error_after_routing_fails_closed_with_router_null(monkeypatch, caplog):
    route_calls = []
    real_route = safety.route
    monkeypatch.setattr(safety, "route", lambda q: route_calls.append(1) or real_route(q))
    def broken(_q):  # the knowledge lookup fails after routing
        raise KeyError("x")
    monkeypatch.setattr(knowledge, "retrieve", broken)
    with caplog.at_level(logging.ERROR, logger="querymate.pipeline"):
        result = pipeline.respond("What is LDL cholesterol?")
    assert route_calls == [1]  # the router did run and decide PROCEED...
    assert_fail_closed(result)  # ...but the reply is not based on that decision
    assert result.kind != "mock_answer"
    assert "(KeyError)" in caplog.text


def test_template_failure_after_routing_fails_closed_with_router_null(monkeypatch):
    broken = {k: v for k, v in pipeline.TEMPLATES.items() if k != "emergency"}
    monkeypatch.setattr(pipeline, "TEMPLATES", broken)  # template lookup fails after routing
    assert_fail_closed(pipeline.respond(ROUTE_EXAMPLES[Route.EMERGENCY]))


def test_successful_replies_log_nothing(caplog):
    with caplog.at_level(logging.DEBUG, logger="querymate.pipeline"):
        for question in ROUTE_EXAMPLES.values():
            pipeline.respond(question)
    assert caplog.records == []


# --- Curated answers after PROCEED (Phase D) ---------------------------------------------------

HYDRATION = "Why is staying hydrated important?"
# Hydration wording plus a signal for each route: the safety route must win.
HYDRATION_WITH_SIGNAL = {
    Route.CRISIS: f"{HYDRATION} I want to kill myself",
    Route.EMERGENCY: f"I have chest pain. {HYDRATION}",
    Route.DOSAGE: f"{HYDRATION} What dose of statin should I take?",
    Route.DIAGNOSIS: f"{HYDRATION} Do I have dehydration?",
    Route.SAFE_FALLBACK: f"Guarantee this. {HYDRATION}",
    Route.OUT_OF_SCOPE: "Why is hydration important for my dog?",
    Route.INVALID_INPUT: f"{HYDRATION} " + "word " * 300,
}


def forbid_retrieval(monkeypatch):
    def forbidden(_q):
        raise AssertionError("retrieval must only run after PROCEED")
    monkeypatch.setattr(knowledge, "retrieve", forbidden)


def test_hydration_question_gets_the_curated_answer():
    entry = knowledge.retrieve(HYDRATION)
    result = pipeline.respond(HYDRATION)
    assert (result.kind, result.title, result.paragraphs) == ("curated_answer", entry.title, entry.paragraphs)
    assert result.content_source == "curated_owner_reviewed" and result.is_mock is False
    assert result.sources == entry.sources and len(result.sources) == 3
    assert result.review_status == "owner_reviewed"
    assert_contract_invariants(result)
    assert result.knowledge_version == "0.1.0" and result.router_version == "0.1.1"


@pytest.mark.parametrize("question", [
    "What is LDL cholesterol?", "Why is sleep important?", "Why is staying hydrated important for babies?",
    "Why is staying hydrated important? I feel dizzy and confused", "My baby is dehydrated",
    "Why is staying hydrated not important?", "Does staying hydrated cure kidney stones?",
])
def test_proceed_without_a_curated_entry_gets_the_exact_safe_fallback(question):
    assert safety.route(question).route is Route.PROCEED
    result = pipeline.respond(question)
    template = pipeline.TEMPLATES["safe_fallback"]
    assert (result.kind, result.title, result.paragraphs) == ("safe_fallback", template.title, template.paragraphs)
    assert result.router_version == "0.1.1"  # the router did decide; this is not a failure
    assert (result.sources, result.review_status, result.knowledge_version) == ((), None, None)


def test_proceed_never_returns_the_mock_answer():
    for question in (HYDRATION, "What is LDL cholesterol?"):
        assert pipeline.respond(question).kind != "mock_answer"


@pytest.mark.parametrize("route", [r for r in Route if r is not Route.PROCEED], ids=lambda r: r.name)
def test_retrieval_is_never_called_on_any_other_route(route, monkeypatch):
    forbid_retrieval(monkeypatch)
    result = pipeline.respond(ROUTE_EXAMPLES[route])
    assert result.router_version == "0.1.1"  # no fail-closed: retrieval really was not called
    assert result.kind == pipeline.TEMPLATES[EXPECTED_KEY[route]].kind


@pytest.mark.parametrize("route", list(HYDRATION_WITH_SIGNAL), ids=lambda r: r.name)
def test_safety_routes_win_over_hydration_wording(route, monkeypatch):
    question = HYDRATION_WITH_SIGNAL[route]
    assert safety.route(question).route is route
    forbid_retrieval(monkeypatch)
    result = pipeline.respond(question)
    key = "invalid_input:too_long" if route is Route.INVALID_INPUT else EXPECTED_KEY[route]
    template = pipeline.TEMPLATES[key]
    assert (result.kind, result.title, result.paragraphs) == (template.kind, template.title, template.paragraphs)
    assert (result.sources, result.review_status, result.knowledge_version) == ((), None, None)


@pytest.mark.parametrize("decision", [
    RouteDecision(Route.PROCEED, ("made:up",)),
    RouteDecision(Route.PROCEED, ("scope:health_vocabulary_no_risk_rule",), router_version="9.9.9"),
    RouteDecision(Route.PROCEED, ("router:error",)),
], ids=["unknown_code", "unapproved_version", "router_error"])
def test_retrieval_is_not_called_after_a_bad_proceed_decision(decision, monkeypatch):
    monkeypatch.setattr(safety, "route", lambda q: decision)
    forbid_retrieval(monkeypatch)
    assert_fail_closed(pipeline.respond(HYDRATION))


def test_unavailable_knowledge_fails_closed(monkeypatch, caplog):
    monkeypatch.setattr(knowledge, "_ENTRIES", None)
    with caplog.at_level(logging.ERROR, logger="querymate.pipeline"):
        assert_fail_closed(pipeline.respond(HYDRATION))
    assert "(KnowledgeUnavailable)" in caplog.text


def test_unavailable_knowledge_leaves_safety_routes_unchanged(monkeypatch):
    monkeypatch.setattr(knowledge, "_ENTRIES", None)
    assert pipeline.respond(ROUTE_EXAMPLES[Route.EMERGENCY]).kind == "emergency"
    assert pipeline.respond(ROUTE_EXAMPLES[Route.CRISIS]).kind == "crisis"


@pytest.mark.parametrize("changes", [{"review_status": "pending_owner_review"}, {"sources": ()}],
                         ids=["pending_review", "no_sources"])
def test_entry_that_may_not_be_displayed_fails_closed(changes, monkeypatch):
    entry = dataclasses.replace(knowledge.retrieve(HYDRATION), **changes)
    monkeypatch.setattr(knowledge, "retrieve", lambda q: entry)
    assert_fail_closed(pipeline.respond(HYDRATION))


def test_curated_answers_log_nothing(caplog):
    with caplog.at_level(logging.DEBUG, logger="querymate.pipeline"):
        pipeline.respond(HYDRATION)
    assert caplog.records == []


def test_curated_replies_never_echo_the_question():
    assert MARKER not in json.dumps(pipeline.respond(f"{HYDRATION} {MARKER}").to_dict("rid"))


# --- 12, 13. Contract invariants, no echo ---------------------------------------------------

@pytest.mark.parametrize("route", list(Route), ids=lambda r: r.name)
def test_replies_never_echo_the_question(route):
    question = f"{ROUTE_EXAMPLES[route]} {MARKER}" if route is not Route.INVALID_INPUT else MARKER * 100
    result = pipeline.respond(question)
    assert MARKER not in json.dumps(result.to_dict("rid"))


def test_to_dict_has_exactly_the_contract_fields():
    body = pipeline.respond("What is LDL cholesterol?").to_dict("abc")
    assert list(body) == ["api_version", "request_id", "kind", "content_source", "message", "sources",
                          "review_status", "is_mock", "abstained", "abstain_reason", "disclaimer", "versions"]
    assert body["request_id"] == "abc"
    assert list(body["message"]) == ["title", "paragraphs"]
    assert list(body["versions"]) == ["router", "matcher", "content", "knowledge"]


def test_curated_sources_serialise_with_exactly_the_contract_fields():
    body = pipeline.respond("Why is staying hydrated important?").to_dict("abc")
    assert len(body["sources"]) == 3
    for source in body["sources"]:
        assert list(source) == ["title", "organization", "url"]
        assert source["url"].startswith("https://")


def test_is_mock_true_only_for_the_mock_placeholder():
    for template in pipeline.TEMPLATES.values():
        result = pipeline.ChatResult(template.kind, template.title, template.paragraphs, "0.1.1")
        assert result.is_mock is (template.kind == "mock_answer")
        assert_contract_invariants(result)


# --- 15. Stateless ------------------------------------------------------------------------------

def test_pipeline_is_stateless_and_results_are_immutable():
    first = [pipeline.respond(q) for q in ROUTE_EXAMPLES.values()]
    pipeline.respond(None)
    pipeline.respond("a" * 5000)
    second = [pipeline.respond(q) for q in reversed(list(ROUTE_EXAMPLES.values()))]
    assert first == list(reversed(second))

    result = first[0]
    with pytest.raises(AttributeError):
        result.kind = "mock_answer"  # frozen
    body = result.to_dict("rid")
    body["message"]["paragraphs"].append("changed")
    assert "changed" not in result.paragraphs
    assert "changed" not in pipeline.respond(ROUTE_EXAMPLES[Route.PROCEED]).paragraphs
