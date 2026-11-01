"""About page: purpose, limitations, and privacy."""

import streamlit as st

from querymate.ui import content

st.title("About HealthChat AI")
st.markdown(f"{content.DESCRIPTION}. {content.TAGLINE}")
st.info(content.PROTOTYPE_NOTICE, icon=":material/school:")

with st.container(horizontal=True):
    with st.container(border=True):
        st.markdown(":blue[:material/menu_book:] **Educational focus**")
        st.caption("General information to help you learn, not personal medical advice.")
    with st.container(border=True):
        st.markdown(":blue[:material/health_and_safety:] **Safety-aware**")
        st.caption("Designed to check input and give safety guidance before anything else.")
    with st.container(border=True):
        st.markdown(":blue[:material/visibility:] **Transparent**")
        st.caption("A solo learning project built with Python, Streamlit, and NLP.")

st.subheader("Current status")
st.markdown(
    "This is a **UI-only preview**. The interface is not connected to any answer "
    "system, and every reply is a labelled mock placeholder."
)

st.subheader("Privacy")
st.markdown(
    "- Chats are kept only in your current browser session and are never saved.\n"
    "- No questions are sent to external AI services.\n"
    "- Usage statistics collection is turned off."
)

st.subheader("Important")
st.markdown(content.DISCLAIMER)
