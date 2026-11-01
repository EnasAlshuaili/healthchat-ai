"""UI-only preview: mock replies, input validation, separation from the backend, and app rendering."""

import ast
import csv
import inspect
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from querymate import config
from querymate.ui import content
from querymate.ui.mock_responses import ReplyKind, mock_reply, validate_question

APP = str(config.PROJECT_ROOT / "app.py")
UI_FILES = [
    config.PROJECT_ROOT / "app.py",
    *sorted((config.PROJECT_ROOT / "app_pages").glob("*.py")),
    *sorted((config.PROJECT_ROOT / "src" / "querymate" / "ui").glob("*.py")),
]
BACKEND_MODULES = {
    "safety", "safety_eval", "topic_matcher", "topic_eval", "retrieval",
    "retrieval_eval", "curated", "cleaning", "audit",
}


# --- Mock replies -----------------------------------------------------------

@pytest.mark.parametrize("kind", list(ReplyKind))
def test_every_mock_reply_is_labelled_mock(kind):
    reply = mock_reply(kind)
    assert reply.is_mock
    assert reply.title.startswith("Mock response")


def test_mock_reply_never_receives_the_question():
    assert list(inspect.signature(mock_reply).parameters) == ["kind"]


def test_emergency_preview_uses_generic_wording():
    text = " ".join(mock_reply(ReplyKind.EMERGENCY).paragraphs)
    assert "local emergency services" in text
    assert "not** triggered by your message" in text


# --- Input validation -------------------------------------------------------

@pytest.mark.parametrize("text", [None, "", "   ", "\n\t"])
def test_empty_input_rejected(text):
    assert validate_question(text) == "Please enter a question."


def test_too_long_input_rejected():
    assert "too long" in validate_question("a" * (config.MAX_INPUT_CHARS + 1))


def test_input_at_limit_accepted():
    assert validate_question("a" * config.MAX_INPUT_CHARS) is None


# --- Separation and content safety -----------------------------------------

@pytest.mark.parametrize("path", UI_FILES, ids=lambda p: p.name)
def test_ui_does_not_import_backend_or_data(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
    parts = {part for name in imported for part in name.split(".")}
    assert not parts & BACKEND_MODULES
    assert not parts & {"pandas", "pyarrow", "sklearn"}


def _luminance(hex_color: str) -> float:
    rgb = [int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    rgb = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def _contrast(fg: str, bg: str) -> float:
    hi, lo = sorted([_luminance(fg), _luminance(bg)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _blend(fg: str, bg: str, alpha: float) -> str:
    f, b = fg.lstrip("#"), bg.lstrip("#")
    return "".join(f"{round(alpha * int(f[i:i + 2], 16) + (1 - alpha) * int(b[i:i + 2], 16)):02X}"
                   for i in (0, 2, 4))


def test_theme_text_meets_wcag_aa():
    import tomllib

    with open(config.PROJECT_ROOT / ".streamlit" / "config.toml", "rb") as f:
        theme = tomllib.load(f)["theme"]
    text = theme["textColor"]
    keys = ("backgroundColor", "secondaryBackgroundColor")
    for bg in [theme[k] for k in keys] + [theme["sidebar"][k] for k in keys]:
        # Streamlit draws st.caption in textColor at 60% opacity (the disclaimer and safety notice use it).
        assert _contrast(_blend(text, bg, 0.6), bg) >= 4.5, bg
    assert _contrast("#FFFFFF", theme["primaryColor"]) >= 4.5  # primary button label


def test_suggested_questions_are_not_evaluation_questions():
    eval_questions = set()
    for name in ("validation_questions.csv", "test_questions.csv"):
        with open(config.EVAL_DIR / name, encoding="utf-8", newline="") as f:
            eval_questions.update(row["question"].strip().lower() for row in csv.DictReader(f))
    assert not {q.lower() for q in content.SUGGESTED_QUESTIONS} & eval_questions


# --- App rendering (headless) -----------------------------------------------

def run_app() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=10).run()
    assert not at.exception
    return at


def test_empty_state_shows_welcome_disclaimer_and_suggestions():
    at = run_app()
    assert at.title[0].value == "Hello! I'm HealthChat AI"
    assert any(content.DISCLAIMER in c.value for c in at.caption)
    assert any("Safety notice" in m.value for m in at.sidebar.markdown)
    assert any(content.MOCK_NOTICE == i.value for i in at.info)
    assert not at.chat_message


def test_question_gets_labelled_mock_reply():
    at = run_app()
    at.chat_input[0].set_value("Why is staying hydrated important?").run()
    assert not at.exception
    messages = at.session_state["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["kind"] == ReplyKind.PLACEHOLDER
    assert len(at.chat_message) == 2
    assert "Mock response" in at.chat_message[1].markdown[0].value


def test_suggested_question_starts_chat():
    at = run_app()
    at.button_group(key="suggestion").set_value(content.SUGGESTED_QUESTIONS[0]).run()
    assert not at.exception
    assert at.session_state["messages"][0]["content"] == content.SUGGESTED_QUESTIONS[0]
    assert len(at.chat_message) == 2
    assert not at.title  # welcome screen replaced by the conversation


def test_emergency_preview_state_renders_as_error_alert():
    at = run_app()
    at.button_group(key="preview_kind").set_value(ReplyKind.EMERGENCY).run()
    at.chat_input[0].set_value("What is good sleep hygiene?").run()
    assert not at.exception
    assert "emergency notice" in at.error[0].value


def test_whitespace_question_shows_validation_message():
    at = run_app()
    at.chat_input[0].set_value("   ").run()
    assert not at.exception
    assert at.session_state["messages"] == []
    assert at.warning[0].value == "Please enter a question."


def test_too_long_question_is_not_sent():
    at = run_app()
    at.chat_input[0].set_value("a" * (config.MAX_INPUT_CHARS + 1)).run()
    assert at.session_state["messages"] == []
    assert "too long" in at.warning[0].value


def test_new_chat_clears_conversation():
    at = run_app()
    at.chat_input[0].set_value("What is good sleep hygiene?").run()
    at.button(key="new_chat").click().run()
    assert not at.exception
    assert at.session_state["messages"] == []
    assert at.title[0].value == "Hello! I'm HealthChat AI"


@pytest.mark.parametrize("page", ["app_pages/about.py", "app_pages/how_it_works.py"])
def test_secondary_pages_render(page):
    at = run_app()
    at.switch_page(page).run()
    assert not at.exception
    assert at.title
