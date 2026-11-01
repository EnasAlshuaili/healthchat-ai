"""Static interface copy for the QueryMate UI (see docs/06_UI_UX_Design.md §4)."""

APP_NAME = "QueryMate"
TAGLINE = "General healthcare information"

# Verbatim from docs/06_UI_UX_Design.md §2 "Disclaimer".
DISCLAIMER = (
    "QueryMate provides general health information and is not a substitute for "
    "professional medical advice, diagnosis, or treatment. If you think you may be "
    "experiencing an emergency, contact local emergency services immediately."
)

# Generic emergency wording only (D-07).
SAFETY_NOTICE = (
    "Do not use QueryMate for emergencies. If you think you or someone else may be "
    "in immediate danger, contact your local emergency services."
)

PROTOTYPE_NOTICE = (
    "QueryMate is a solo educational prototype. It is not a doctor, does not diagnose "
    "or prescribe, and has not been clinically reviewed or validated."
)

MOCK_NOTICE = (
    "**UI preview:** QueryMate is not yet connected to its answer system. "
    "Every reply in this preview is a labelled mock placeholder and contains no "
    "medical information."
)

WELCOME = (
    "I'm QueryMate, an educational assistant for general healthcare information. "
    "What would you like to learn about today?"
)

INPUT_PLACEHOLDER = "Ask a general health question…"
PRIVACY_HINT = "Please don't include names, ID numbers, addresses, or other personal details."
LOADING_TEXT = "Preparing a mock response…"
CHATS_NOT_SAVED = "Chats are not saved. Starting a new chat clears this conversation."

# Example prompts for the empty state. Chosen to avoid copying questions from
# eval/validation_questions.csv and eval/test_questions.csv.
SUGGESTED_QUESTIONS = (
    "Why is staying hydrated important?",
    "What is good sleep hygiene?",
    "What does a balanced diet include?",
    "How does regular exercise support health?",
)

# (icon, title, text) for the welcome cards. Describes planned behaviour only.
FEATURES = (
    (
        ":material/menu_book:",
        "General information",
        "Plain-language explanations of common health topics.",
    ),
    (
        ":material/health_and_safety:",
        "Safety checks first",
        "Emergency and personal-advice questions are handled before anything else.",
    ),
    (
        ":material/fact_check:",
        "Honest about limits",
        "When no reviewed content fits, QueryMate says so instead of guessing.",
    ),
)
