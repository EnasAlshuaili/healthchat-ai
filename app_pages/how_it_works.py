"""How it works page: the planned pipeline, clearly marked as not yet connected."""

import streamlit as st

st.title("How it works")
st.markdown("How HealthChat AI is designed to handle a question once the interface is connected.")
st.warning(
    "**Not connected yet.** In this UI preview, none of the steps below run. "
    "Replies are labelled mock placeholders.",
    icon=":material/construction:",
)

STEPS = (
    (
        ":material/edit_note:",
        "1. You ask a question",
        "Type a general health question. Avoid personal details.",
    ),
    (
        ":material/health_and_safety:",
        "2. Safety checks run first",
        "Possible emergencies, dosage and diagnosis requests, and out-of-scope "
        "questions get safety guidance instead of an answer.",
    ),
    (
        ":material/manage_search:",
        "3. Reviewed content is matched",
        "Your question is compared with a small set of educational topics. "
        "If nothing fits well, you get a safe fallback instead of a guess.",
    ),
)

with st.container(horizontal=True):
    for icon, title, text in STEPS:
        with st.container(border=True):
            st.markdown(f"### :blue[{icon}]")
            st.markdown(f"**{title}**")
            st.caption(text)

st.subheader("What HealthChat AI will not do")
st.markdown(
    "- Show raw answers from the original dataset.\n"
    "- Diagnose conditions, recommend medicines, or suggest doses.\n"
    "- Send your questions to external AI services."
)
