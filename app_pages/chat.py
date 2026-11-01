"""Chat page. Replies come only from querymate.ui.mock_responses (no backend)."""

import time

import streamlit as st

from querymate import config
from querymate.ui import content
from querymate.ui.mock_responses import ReplyKind, mock_reply, validate_question

ASSISTANT_AVATAR = ":material/smart_toy:"
USER_AVATAR = ":material/person:"
MOCK_DELAY_SECONDS = 0.6  # Simulated wait so the loading state is visible.

PREVIEW_LABELS = {
    ReplyKind.PLACEHOLDER: "Placeholder",
    ReplyKind.FALLBACK: "No answer",
    ReplyKind.EMERGENCY: "Emergency",
    ReplyKind.ERROR: "Error",
}


def add_question(text: str | None) -> None:
    error = validate_question(text)
    if error:
        st.session_state.input_error = error
    else:
        st.session_state.messages.append({"role": "user", "content": text.strip()})


def on_submit() -> None:
    add_question(st.session_state.chat_input)


def on_suggestion() -> None:
    if st.session_state.suggestion:
        add_question(st.session_state.suggestion)


def render_reply(kind: ReplyKind) -> None:
    reply = mock_reply(kind)
    st.badge("Mock response", icon=":material/science:", color="gray")
    text = f"**{reply.title}**\n\n" + "\n\n".join(reply.paragraphs)
    # Each state carries an icon and a text title, so meaning never relies on colour alone.
    if kind == ReplyKind.EMERGENCY:
        st.error(text, icon=":material/emergency:")
    elif kind == ReplyKind.ERROR:
        st.warning(text, icon=":material/cloud_off:")
    elif kind == ReplyKind.FALLBACK:
        st.info(text, icon=":material/help:")
    else:
        st.markdown(text)


def render_message(message: dict) -> None:
    if message["role"] == "user":
        with st.chat_message("user", avatar=USER_AVATAR):
            st.text(message["content"])
    else:
        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            render_reply(message["kind"])


with st.sidebar:
    with st.expander("UI state preview", icon=":material/tune:"):
        preview_kind = st.segmented_control(
            "Mock reply style",
            options=list(ReplyKind),
            format_func=PREVIEW_LABELS.get,
            default=ReplyKind.PLACEHOLDER,
            key="preview_kind",
            help="For reviewing the design only. Chooses which mock state the next "
            "reply shows; your message is never analysed.",
        )
preview_kind = preview_kind or ReplyKind.PLACEHOLDER

st.chat_input(
    content.INPUT_PLACEHOLDER,
    max_chars=config.MAX_INPUT_CHARS,
    submit_mode="disable",
    key="chat_input",
    on_submit=on_submit,
)

messages = st.session_state.messages

if not messages:
    # Empty state: welcome, what HealthChat AI aims to do, and example questions.
    st.badge("Educational prototype", icon=":material/school:", color="blue")
    st.title("Hello! I'm HealthChat AI")
    st.markdown(content.WELCOME)
    st.info(content.MOCK_NOTICE, icon=":material/construction:")

    with st.container(horizontal=True, key="features"):
        for icon, title, text in content.FEATURES:
            with st.container(border=True):
                st.markdown(f":blue[{icon}] **{title}**")
                st.caption(text)

    st.pills(
        "Try an example question",
        content.SUGGESTED_QUESTIONS,
        key="suggestion",
        on_change=on_suggestion,
    )
else:
    for message in messages:
        render_message(message)

    if messages[-1]["role"] == "user":
        # Loading state, then a static mock reply. The question is never passed on.
        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            with st.spinner(content.LOADING_TEXT):
                time.sleep(MOCK_DELAY_SECONDS)
            render_reply(preview_kind)
        messages.append({"role": "assistant", "kind": preview_kind})

if error := st.session_state.pop("input_error", None):
    st.warning(error, icon=":material/error:")

st.caption(f":material/info: {content.DISCLAIMER} {content.PRIVACY_HINT}")
