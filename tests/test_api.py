"""API Contract v0.3, curated_single_topic mode (docs/API_CONTRACT.md).

The API delegates every question to querymate.pipeline; these tests check the HTTP
layer (validation, errors, headers, privacy) and that responses are exactly the
pipeline's approved replies in the v0.3 shape.
"""

import ast
import importlib.util
import json
import logging
import re
import subprocess
import sys
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from querymate import config, knowledge, pipeline, safety
from querymate.api import main
from querymate.api.errors import MAX_BODY_BYTES, MESSAGES
from querymate.api.schemas import ChatResponse
from querymate.safety import Route
from querymate.ui.content import DISCLAIMER

API_DIR = config.PROJECT_ROOT / "src" / "querymate" / "api"
CONTRACT = (config.PROJECT_ROOT / "docs" / "API_CONTRACT.md").read_text(encoding="utf-8")
MARKER = "ZZQ-MARKER-7f3a"  # unique text that must never appear in any response or log
CHAT_FIELDS = ["api_version", "request_id", "kind", "content_source", "message", "sources", "review_status",
               "is_mock", "abstained", "abstain_reason", "disclaimer", "versions"]
HYDRATION = "Why is staying hydrated important?"
JSON = {"Content-Type": "application/json"}

ROUTE_EXAMPLES = {  # real router inputs, as in tests/test_pipeline.py
    Route.PROCEED: ("What is LDL cholesterol?", "safe_fallback"),  # no curated entry (D-02)
    Route.CRISIS: ("I want to kill myself, what is cholesterol", "crisis"),
    Route.EMERGENCY: ("I have chest pain, what is LDL cholesterol?", "emergency"),
    Route.DOSAGE: ("What dose of statin lowers LDL cholesterol?", "decline_dosage"),
    Route.DIAGNOSIS: ("Do I have high cholesterol?", "decline_diagnosis"),
    Route.SAFE_FALLBACK: ("Guarantee that LDL cholesterol is bad", "safe_fallback"),
    Route.OUT_OF_SCOPE: ("My dog has high cholesterol", "out_of_scope"),
    Route.INVALID_INPUT: ("   ", "invalid_input"),
}


@pytest.fixture
def client():
    with TestClient(main.create_app(), raise_server_exceptions=False) as c:
        yield c


def chat(client, body, headers=JSON):
    data = body if isinstance(body, (bytes, str)) else json.dumps(body)
    return client.post("/api/chat", content=data, headers=headers)


def assert_error(response, status, code):
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"} and set(body["error"]) == {"code", "message", "request_id"}
    assert body["error"]["code"] == code
    assert body["error"]["message"] == MESSAGES[code]
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]
    assert response.headers["Cache-Control"] == "no-store"
    assert MARKER not in response.text


def assert_v03(body):
    assert list(body) == CHAT_FIELDS
    assert body["api_version"] == "0.3"
    assert body["is_mock"] is (body["kind"] == "mock_answer")
    expected_source = {"curated_answer": "curated_owner_reviewed", "mock_answer": "mock_placeholder",
                       "invalid_input": "input_check"}
    assert body["content_source"] == expected_source.get(body["kind"], "safety_template")
    assert body["abstained"] is False and body["abstain_reason"] is None
    assert body["disclaimer"] == DISCLAIMER
    assert body["versions"]["matcher"] is None and body["versions"]["content"] == "templates-0.1"
    if body["kind"] == "curated_answer":
        assert body["sources"] and body["review_status"] == "owner_reviewed"
        assert body["versions"]["knowledge"] == "0.1.0"
    else:
        assert body["sources"] == [] and body["review_status"] is None and body["versions"]["knowledge"] is None


# --- Success and the v0.3 schema ---------------------------------------------------------------

def test_chat_returns_v03_schema(client):
    r = chat(client, {"question": "What is LDL cholesterol?"})
    assert r.status_code == 200
    body = r.json()
    assert_v03(body)
    assert body["kind"] == "safe_fallback" and body["is_mock"] is False
    assert body["versions"] == {"router": "0.1.1", "matcher": None, "content": "templates-0.1", "knowledge": None}
    assert body["message"]["paragraphs"] == list(pipeline.TEMPLATES["safe_fallback"].paragraphs)


# --- Curated answers (Phase D) -----------------------------------------------------------------

def test_hydration_question_gets_the_curated_answer_and_sources(client):
    r = chat(client, {"question": HYDRATION})
    assert r.status_code == 200
    body = r.json()
    assert_v03(body)
    entry = knowledge.retrieve(HYDRATION)
    assert body["kind"] == "curated_answer" and body["is_mock"] is False
    assert body["content_source"] == "curated_owner_reviewed"
    assert body["message"] == {"title": entry.title, "paragraphs": list(entry.paragraphs)}
    assert body["sources"] == [
        {"title": "About Water and Healthier Drinks", "organization": "Centers for Disease Control and Prevention (CDC)",
         "url": "https://www.cdc.gov/healthy-weight-growth/water-healthy-drinks/"},
        {"title": "Water, drinks and hydration", "organization": "NHS",
         "url": "https://www.nhs.uk/Live-well/eat-well/food-guidelines-and-food-labels/water-drinks-nutrition/"},
        {"title": "Dehydration", "organization": "NHS", "url": "https://www.nhs.uk/conditions/dehydration/"},
    ]
    assert body["versions"] == {"router": "0.1.1", "matcher": None, "content": "templates-0.1", "knowledge": "0.1.0"}


def test_curated_reply_states_it_is_not_clinically_reviewed(client):
    r = chat(client, {"question": HYDRATION})
    assert "has not been clinically reviewed or clinically validated" in r.json()["message"]["paragraphs"][3]
    assert "reviewed_content" not in r.text


@pytest.mark.parametrize("question, kind, template", [
    (f"{HYDRATION} I want to kill myself", "crisis", "crisis"),
    (f"I have chest pain. {HYDRATION}", "emergency", "emergency"),
    (f"{HYDRATION} What dose of statin should I take?", "decline_dosage", "decline_dosage"),
    (f"{HYDRATION} Do I have dehydration?", "decline_diagnosis", "decline_diagnosis"),
    (f"Guarantee this. {HYDRATION}", "safe_fallback", "safe_fallback"),
    ("Why is hydration important for my dog?", "out_of_scope", "out_of_scope"),
], ids=["crisis", "emergency", "dosage", "diagnosis", "safe_fallback", "out_of_scope"])
def test_unsafe_hydration_questions_keep_their_exact_approved_messages(client, monkeypatch, question, kind, template):
    def forbidden(_q):
        raise AssertionError("retrieval must only run after PROCEED")
    monkeypatch.setattr(knowledge, "retrieve", forbidden)
    body = chat(client, {"question": question}).json()
    assert_v03(body)
    approved = pipeline.TEMPLATES[template]
    assert body["kind"] == kind and body["content_source"] == "safety_template"
    assert body["message"] == {"title": approved.title, "paragraphs": list(approved.paragraphs)}
    assert body["sources"] == [] and body["versions"]["router"] == "0.1.1"


@pytest.mark.parametrize("question", ["Why is staying hydrated important for babies?", "My baby is dehydrated",
                                      "Why is sleep important?"])
def test_questions_without_a_curated_entry_get_the_safe_fallback(client, question):
    body = chat(client, {"question": question}).json()
    assert_v03(body)
    assert body["kind"] == "safe_fallback" and body["sources"] == []
    assert body["message"]["paragraphs"] == list(pipeline.TEMPLATES["safe_fallback"].paragraphs)
    assert body["versions"]["router"] == "0.1.1"


def test_unavailable_knowledge_fails_closed_through_the_api(client, monkeypatch):
    monkeypatch.setattr(knowledge, "_ENTRIES", None)
    body = chat(client, {"question": HYDRATION}).json()
    assert_v03(body)
    assert body["kind"] == "safe_fallback" and body["versions"]["router"] is None
    assert client.get("/api/health").json()["versions"]["knowledge"] is None
    assert chat(client, {"question": ROUTE_EXAMPLES[Route.EMERGENCY][0]}).json()["kind"] == "emergency"


@pytest.mark.parametrize("route", list(Route), ids=lambda r: r.name)
def test_every_route_returns_the_pipelines_approved_reply(client, route):
    question, kind = ROUTE_EXAMPLES[route]
    body = chat(client, {"question": question}).json()
    assert_v03(body)
    assert body["kind"] == kind
    # The API serves exactly the pipeline's reply: no routing or templates of its own.
    assert body == pipeline.respond(question).to_dict(body["request_id"])
    assert body["versions"]["router"] == "0.1.1"


def test_emergency_and_crisis_wording_through_the_api(client):
    emergency = chat(client, {"question": ROUTE_EXAMPLES[Route.EMERGENCY][0]}).json()["message"]
    crisis = chat(client, {"question": ROUTE_EXAMPLES[Route.CRISIS][0]}).json()["message"]
    assert emergency["paragraphs"] == list(pipeline.TEMPLATES["emergency"].paragraphs)
    assert crisis["paragraphs"][:2] == emergency["paragraphs"]  # emergency first, unchanged
    assert crisis["paragraphs"][2] == pipeline.TEMPLATES["crisis"].paragraphs[2]
    assert (emergency["title"], crisis["title"]) == ("Possible emergency", "Please get help now")


def test_documented_example_payloads_are_served(client, monkeypatch):
    inputs = {k: q for q, k in ROUTE_EXAMPLES.values()} | {"curated_answer": HYDRATION}
    for block in re.findall(r"```json\n(.*?)```", CONTRACT, re.S):
        try:
            example = json.loads(block)
        except json.JSONDecodeError:
            continue  # the diagnostics fragment
        if "kind" in example:
            body = chat(client, {"question": inputs[example["kind"]]}).json()
            assert body == {**example, "request_id": body["request_id"]}
        elif "status" in example:
            assert client.get("/api/health").json() == example


def test_request_id_is_uuid4_and_matches_header(client):
    r = chat(client, {"question": "What is good sleep hygiene?"})
    assert r.json()["request_id"] == r.headers["X-Request-ID"]
    assert uuid.UUID(r.headers["X-Request-ID"]).version == 4
    assert r.headers["X-Request-ID"] != chat(client, {"question": "x y"}).headers["X-Request-ID"]


def test_no_store_and_no_cookies(client):
    r = chat(client, {"question": "What is fibre?"})
    assert r.headers["Cache-Control"] == "no-store"
    assert "set-cookie" not in r.headers


def test_charset_parameter_accepted(client):
    r = chat(client, {"question": "What is fibre?"},
             headers={"Content-Type": "application/json; charset=utf-8"})
    assert r.status_code == 200


# --- Replies depend only on the route and an exact curated match --------------------------------

def test_unmatched_proceed_questions_get_identical_replies(client):
    a = chat(client, {"question": "What is LDL cholesterol?"}).json()
    b = chat(client, {"question": "Why is sleep important?"}).json()
    assert a["kind"] == b["kind"] == "safe_fallback"
    assert a["message"] == b["message"]


def test_approved_wordings_of_one_entry_get_identical_replies(client):
    a = chat(client, {"question": HYDRATION}).json()
    b = chat(client, {"question": "Why is staying hydrated important for the body?"}).json()
    assert a["kind"] == b["kind"] == "curated_answer"
    assert (a["message"], a["sources"]) == (b["message"], b["sources"])


@pytest.mark.parametrize("route", list(Route), ids=lambda r: r.name)
def test_reply_never_contains_question(client, route):
    question = ROUTE_EXAMPLES[route][0]
    question = f"{question} {MARKER}" if route is not Route.INVALID_INPUT else MARKER * 100
    r = chat(client, {"question": question})
    assert r.status_code == 200 and MARKER not in r.text


def test_curated_reply_never_contains_question(client):
    r = chat(client, {"question": HYDRATION})
    assert r.json()["kind"] == "curated_answer" and HYDRATION not in r.text


# --- Input checks (200 invalid_input, decided by the router) -----------------------------------

@pytest.mark.parametrize("question", ["", "   ", "\n\t "])
def test_empty_question_is_invalid_input(client, question):
    body = chat(client, {"question": question}).json()
    assert body["kind"] == "invalid_input" and body["is_mock"] is False
    assert body["content_source"] == "input_check"
    assert body["message"]["title"] == "Please enter a question."


def test_question_at_limit_is_accepted(client):
    question = "What is fibre? " + "a" * (config.MAX_INPUT_CHARS - 15)
    assert len(question) == config.MAX_INPUT_CHARS
    body = chat(client, {"question": question}).json()
    assert body["kind"] == "safe_fallback" and body["versions"]["router"] == "0.1.1"


def test_over_length_question_is_invalid_input_with_emergency_line(client):
    body = chat(client, {"question": "a" * (config.MAX_INPUT_CHARS + 1)}).json()
    assert body["kind"] == "invalid_input"
    assert body["message"]["title"] == "Your question is too long."
    assert pipeline.EMERGENCY_LINE in body["message"]["paragraphs"]


def test_length_uses_router_whitespace_normalisation(client):
    padded = "  What is fibre?  " + " \n\t " * 2000
    assert len(padded) > config.MAX_INPUT_CHARS
    body = chat(client, {"question": padded}).json()
    assert body["kind"] == "safe_fallback" and body["versions"]["router"] == "0.1.1"


@pytest.mark.parametrize("prefix, kind", [("I want to kill myself. ", "crisis"),
                                          ("I have chest pain and can't breathe. ", "emergency")])
def test_over_length_question_with_urgent_signal_gets_urgent_reply(client, prefix, kind):
    body = chat(client, {"question": prefix + "word " * 400}).json()
    assert body["kind"] == kind and body["content_source"] == "safety_template"


# --- Request validation (422) -------------------------------------------------------------------

@pytest.mark.parametrize("body", [
    {"question": f"{MARKER}", "extra": MARKER},          # unknown field
    {"question": 123},                                   # wrong type
    {"question": [MARKER]},                              # wrong type
    {"question": None},
    {"text": MARKER},                                    # missing field
    {},
    [MARKER],                                            # not an object
    f'{{"question": "{MARKER}"',                         # malformed JSON
    f"{MARKER} not json",
    "",                                                  # empty body
    b'{"question": "\xff\xfe' + MARKER.encode() + b'"}',  # invalid UTF-8
], ids=["unknown_field", "int", "list", "null", "missing", "empty_object", "array",
        "truncated_json", "not_json", "empty_body", "invalid_utf8"])
def test_malformed_requests_get_422_without_echo(client, body):
    assert_error(chat(client, body), 422, "invalid_request")


@pytest.mark.parametrize("field", ["content_source", "is_mock", "kind", "versions"])
def test_response_fields_cannot_be_sent_in_requests(client, field):
    assert_error(chat(client, {"question": "What is fibre?", field: "x"}), 422, "invalid_request")


# --- Content type (415) -------------------------------------------------------------------------

@pytest.mark.parametrize("headers", [
    {}, {"Content-Type": "text/plain"}, {"Content-Type": "application/x-www-form-urlencoded"},
    {"Content-Type": "application/merge-patch+json"}, {"Content-Type": "multipart/form-data"},
], ids=["missing", "text", "form", "plus_json", "multipart"])
def test_non_json_content_type_gets_415(client, headers):
    r = client.post("/api/chat", content=json.dumps({"question": MARKER}), headers=headers)
    assert_error(r, 415, "unsupported_media_type")


# --- Body size (413) ----------------------------------------------------------------------------

def _body_of_size(n: int) -> bytes:
    prefix, suffix = b'{"question": "', b'"}'
    return prefix + b"a" * (n - len(prefix) - len(suffix)) + suffix


def test_body_at_limit_is_accepted(client):
    body = _body_of_size(MAX_BODY_BYTES)
    assert len(body) == MAX_BODY_BYTES
    r = chat(client, body)
    assert r.status_code == 200 and r.json()["kind"] == "invalid_input"


def test_body_over_limit_gets_413(client):
    assert_error(chat(client, _body_of_size(MAX_BODY_BYTES + 1)), 413, "payload_too_large")


def test_body_over_limit_without_content_length_gets_413(client):
    def chunks():
        yield b'{"question": "'
        for _ in range(MAX_BODY_BYTES // 1024 + 1):
            yield MARKER.encode().ljust(1024, b"a")
        yield b'"}'
    r = client.post("/api/chat", content=chunks(), headers=JSON)
    assert "content-length" not in r.request.headers
    assert_error(r, 413, "payload_too_large")


@pytest.mark.parametrize("char", ["\U0001F600", "\u0001"], ids=["4_byte_utf8", "6_byte_escape"])
def test_twenty_thousand_worst_case_characters_fit(client, char):
    data = json.dumps({"question": char * 20_000}, ensure_ascii=False).encode()
    assert len(data) <= MAX_BODY_BYTES
    assert chat(client, data).json()["kind"] == "invalid_input"


# --- Fail closed and errors -----------------------------------------------------------------------

def test_router_failure_fails_closed_inside_the_pipeline(client, monkeypatch, caplog):
    def boom(_q):
        raise RuntimeError(f"failure while handling {MARKER} at C:/internal/path.py")
    monkeypatch.setattr(safety, "route", boom)
    with caplog.at_level(logging.DEBUG):
        r = chat(client, {"question": MARKER})
    assert r.status_code == 200
    body = r.json()
    assert_v03(body)
    assert body["kind"] == "safe_fallback" and body["versions"]["router"] is None
    assert body["message"]["paragraphs"] == list(pipeline.TEMPLATES["safe_fallback"].paragraphs)
    assert MARKER not in r.text and "RuntimeError" not in r.text and "path" not in r.text
    assert MARKER not in caplog.text and "Traceback" not in caplog.text


def test_router_internal_error_fallback_reports_router_null(client, monkeypatch):
    monkeypatch.setattr(safety, "_route", lambda q: (_ for _ in ()).throw(ValueError("x")))
    body = chat(client, {"question": "What is LDL cholesterol?"}).json()
    assert body["kind"] == "safe_fallback" and body["versions"]["router"] is None


def test_internal_error_outside_pipeline_is_generic_500(client, monkeypatch, caplog):
    def boom(_question):
        raise RuntimeError(f"failure while handling {MARKER}")
    monkeypatch.setattr(pipeline, "respond", boom)
    with caplog.at_level(logging.DEBUG):
        r = chat(client, {"question": MARKER})
    assert_error(r, 500, "internal_error")
    assert "emergency services" in r.json()["error"]["message"]
    assert "Traceback" not in r.text and "RuntimeError" not in r.text
    assert MARKER not in caplog.text and "Traceback" not in caplog.text
    assert "RuntimeError" in caplog.text  # exception type only


def test_response_invariant_violation_is_a_generic_500(client, monkeypatch):
    real = pipeline.respond

    class Broken:
        def __init__(self, result):
            self.result = result

        def to_dict(self, request_id):
            body = self.result.to_dict(request_id)
            body["is_mock"] = not body["is_mock"]  # breaks the is_mock invariant
            return body

    monkeypatch.setattr(pipeline, "respond", lambda q: Broken(real(q)))
    assert_error(chat(client, {"question": "What is LDL cholesterol?"}), 500, "internal_error")


def test_requests_are_not_logged(client, caplog):
    with caplog.at_level(logging.DEBUG):
        for route in Route:
            chat(client, {"question": f"{ROUTE_EXAMPLES[route][0]} {MARKER}"})
        chat(client, {"question": MARKER, "extra": 1})
        chat(client, f"{MARKER} not json")
    assert MARKER not in caplog.text


def test_unknown_path_gets_404(client):
    assert_error(client.get(f"/api/{MARKER}"), 404, "not_found")


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_endpoints_disabled(client, path):
    assert_error(client.get(path), 404, "not_found")


def test_wrong_method_gets_405(client):
    r = client.get("/api/chat")
    assert_error(r, 405, "method_not_allowed")
    assert "POST" in r.headers["Allow"]


# --- Response schema invariants -------------------------------------------------------------------

def _valid_body(**changes):
    body = pipeline.respond(HYDRATION).to_dict("rid")
    for path, value in changes.items():
        target = body
        *parents, leaf = path.split("__")
        for p in parents:
            target = target[p]
        target[leaf] = value
    return body


def test_valid_pipeline_bodies_pass_the_schema():
    for question, _kind in [*ROUTE_EXAMPLES.values(), (HYDRATION, "curated_answer")]:
        ChatResponse.model_validate(pipeline.respond(question).to_dict("rid"))


@pytest.mark.parametrize("changes", [
    {"is_mock": True},                              # only mock_answer is is_mock true
    {"is_mock": "true"},                            # not a boolean
    {"content_source": "safety_template"},          # does not match kind
    {"content_source": "reviewed_content"},         # reserved, not allowed yet
    {"review_status": "pending_owner_review"},      # never displayable
    {"review_status": "clinically_reviewed"},       # never a valid claim (D-11)
    {"review_status": None},                        # curated answers must carry it
    {"sources": []},                                # curated answers must have sources
    {"sources": [{"title": "T", "organization": "O", "url": "http://example.org"}]},  # https only
    {"sources": [{"title": "T", "organization": "O", "url": "javascript:alert(1)"}]},
    {"sources": [{"title": "T", "organization": "O", "url": "https://x.org", "extra": 1}]},
    {"sources": [{"title": "", "organization": "O", "url": "https://x.org"}]},
    {"versions__knowledge": None},                  # curated answers must carry it
    {"versions__router": None},                     # a curated answer needs a router decision
    {"abstained": True},                            # matcher not connected
    {"abstain_reason": "below_min_score"},
    {"versions__matcher": "0.1.0"},
    {"versions__content": "mock"},
    {"api_version": "0.1"},
    {"api_version": "0.2"},
    {"kind": "answer"},                             # unknown kind
    {"message__paragraphs": []},
    {"extra_field": 1},
], ids=lambda c: next(iter(c)))
def test_schema_rejects_contract_violations(changes):
    with pytest.raises(ValidationError):
        ChatResponse.model_validate(_valid_body(**changes))


def _mock_body():
    template = pipeline.TEMPLATES["mock_answer"]
    return pipeline.ChatResult(template.kind, template.title, template.paragraphs, "0.1.1").to_dict("rid")


def test_mock_answer_kind_still_requires_is_mock_true():
    ChatResponse.model_validate(_mock_body())
    with pytest.raises(ValidationError):
        ChatResponse.model_validate({**_mock_body(), "is_mock": False})


SOURCE = {"title": "T", "organization": "O", "url": "https://example.org"}


@pytest.mark.parametrize("route", [r for r in Route if r is not Route.PROCEED], ids=lambda r: r.name)
@pytest.mark.parametrize("changes", [{"sources": [SOURCE]}, {"review_status": "owner_reviewed"}],
                         ids=["sources", "review_status"])
def test_safety_replies_cannot_carry_curated_fields(route, changes):
    body = pipeline.respond(ROUTE_EXAMPLES[route][0]).to_dict("rid")
    with pytest.raises(ValidationError):
        ChatResponse.model_validate({**body, **changes})


def test_safety_reply_cannot_carry_a_knowledge_version():
    body = pipeline.respond(ROUTE_EXAMPLES[Route.EMERGENCY][0]).to_dict("rid")
    body["versions"]["knowledge"] = "0.1.0"
    with pytest.raises(ValidationError):
        ChatResponse.model_validate(body)


def test_safety_reply_with_is_mock_true_is_rejected():
    body = pipeline.respond(ROUTE_EXAMPLES[Route.EMERGENCY][0]).to_dict("rid")
    body["is_mock"] = True
    with pytest.raises(ValidationError):
        ChatResponse.model_validate(body)


# --- Health ---------------------------------------------------------------------------------------

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "api_version": "0.3", "mode": "curated_single_topic",
                        "versions": {"router": "0.1.1", "matcher": None, "content": "templates-0.1",
                                     "knowledge": "0.1.0"}}
    assert r.headers["Cache-Control"] == "no-store"


def test_health_does_not_run_the_router(client, monkeypatch):
    monkeypatch.setattr(safety, "route", lambda q: pytest.fail("health must not route a question"))
    assert client.get("/api/health").json()["versions"]["router"] == "0.1.1"


# --- Separation, privacy, and local-only -----------------------------------------------------------

# The API may now use the router (via the pipeline) but never the matcher, retrieval,
# curated content, evaluation code, the dataset, or network/LLM libraries.
FORBIDDEN_PARTS = {"safety_eval", "topic_matcher", "topic_eval", "retrieval", "retrieval_eval",
                   "curated", "cleaning", "audit", "pandas", "pyarrow", "sklearn", "requests",
                   "urllib", "http", "socket", "openai", "anthropic"}


@pytest.mark.parametrize("path", sorted(API_DIR.glob("*.py")), ids=lambda p: p.name)
def test_api_source_imports_no_matcher_data_or_network_modules(path):
    imported = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not {p for name in imported for p in name.split(".")} & FORBIDDEN_PARTS


def test_importing_api_loads_router_but_not_matcher_or_retrieval():
    code = ("import sys; sys.path.insert(0, 'src'); import querymate.api.main; "
            "print(sorted(m for m in sys.modules if m in {'querymate.topic_matcher', 'querymate.retrieval', "
            "'querymate.curated', 'querymate.retrieval_eval', 'querymate.topic_eval', 'querymate.safety_eval'} "
            "or m.split('.')[0] == 'sklearn')); "
            "print('querymate.pipeline' in sys.modules and 'querymate.safety' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], cwd=config.PROJECT_ROOT,
                         capture_output=True, text=True, check=True)
    assert out.stdout.split() == ["[]", "True"]


_OPENED: list[str] = []
_WATCH = {"on": False}


def _audit(event, args):
    if _WATCH["on"] and event == "open" and args and isinstance(args[0], (str, bytes)):
        _OPENED.append(str(args[0]))


sys.addaudithook(_audit)


def test_requests_open_no_files(client):
    _OPENED.clear()
    _WATCH["on"] = True
    try:
        for question, _kind in [*ROUTE_EXAMPLES.values(), (HYDRATION, "curated_answer")]:
            chat(client, {"question": question})
        client.get("/api/health")
    finally:
        _WATCH["on"] = False
    assert _OPENED == []  # no dataset, index, curated, log, or other file


def test_native_telemetry_off_even_if_env_requests_it(monkeypatch):
    monkeypatch.setenv("FASTAPI_OTEL_AUTO_CONFIGURE", "true")
    app = main.create_app()
    assert app._native_telemetry.enabled() is False  # private FastAPI attribute; fails loudly if it changes
    assert main.TELEMETRY_OFF["auto_configure"] is False


def test_run_script_binds_localhost_without_access_log():
    spec = importlib.util.spec_from_file_location("run_api", config.PROJECT_ROOT / "scripts" / "run_api.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.HOST == "127.0.0.1"
    assert module.ACCESS_LOG is False
