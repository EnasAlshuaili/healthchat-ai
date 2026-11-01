"""QueryMate Streamlit entry point (UI-only preview).

Usage (from the project root):
    .venv\\Scripts\\python.exe -m streamlit run app.py

The interface is not connected to the safety router, topic matcher, retrieval,
or dataset. All assistant replies are labelled mock placeholders
(src/querymate/ui/mock_responses.py).
"""

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from querymate.ui import content  # noqa: E402

st.set_page_config(
    page_title=content.APP_NAME,
    page_icon=str(ROOT / "assets" / "querymate_icon.svg"),
    layout="centered",
)

# FR-14: conversation lives in session state only and is never written to disk.
st.session_state.setdefault("messages", [])

st.logo(
    str(ROOT / "assets" / "querymate_logo.svg"),
    icon_image=str(ROOT / "assets" / "querymate_icon.svg"),
    size="large",
)

chat_page = st.Page("app_pages/chat.py", title="Chat", icon=":material/chat:", default=True)
pg = st.navigation(
    [
        chat_page,
        st.Page("app_pages/how_it_works.py", title="How it works", icon=":material/route:"),
        st.Page("app_pages/about.py", title="About", icon=":material/info:"),
    ]
)

with st.sidebar:
    if st.button("New chat", icon=":material/add:", type="primary", width="stretch", key="new_chat"):
        st.session_state.messages = []
        st.switch_page(chat_page)
    st.caption(content.CHATS_NOT_SAVED)

    with st.container(border=True, key="safety_notice"):
        st.markdown(":red[:material/emergency:] **Safety notice**")
        st.caption(content.SAFETY_NOTICE)

    st.badge("Educational prototype", icon=":material/school:", color="blue")

pg.run()
