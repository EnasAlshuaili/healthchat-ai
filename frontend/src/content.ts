// Static interface copy. Mirrors src/querymate/ui/content.py (Streamlit) and
// docs/06_UI_UX_Design.md so both UIs say the same thing.

export const APP_NAME = "HealthChat AI";
export const DESCRIPTION = "Educational Healthcare Q&A Chatbot";
export const TAGLINE = "Your AI Assistant for General Health Education.";

// Verbatim from docs/06_UI_UX_Design.md §2 "Disclaimer".
export const DISCLAIMER =
  "HealthChat AI provides general health information and is not a substitute for " +
  "professional medical advice, diagnosis, or treatment. If you think you may be " +
  "experiencing an emergency, contact local emergency services immediately.";

// Generic emergency wording only (D-07).
export const EMERGENCY_LINE =
  "If you think you may be experiencing an emergency, contact local emergency services immediately.";

export const SAFETY_NOTICE =
  "Do not use HealthChat AI for emergencies. If you think you or someone else may be " +
  "in immediate danger, contact your local emergency services.";

export const PROTOTYPE_NOTICE =
  "HealthChat AI is a solo educational prototype. It is not a doctor, does not diagnose " +
  "or prescribe, and has not been clinically reviewed or validated.";

// Contract v0.3 (D-21): one curated topic; everything else gets a fixed message.
export const SCOPE_NOTICE =
  "HealthChat AI can answer only a small set of general questions, using educational " +
  "content reviewed by the project owner, not clinically reviewed. Each question first " +
  "goes through an automated, keyword-based safety check (a prototype, not clinical " +
  "triage). Anything else gets a fixed safety message or a safe fallback.";

export const WELCOME =
  "I'm HealthChat AI, an educational assistant for general healthcare information. " +
  "What would you like to learn about today?";

export const INPUT_PLACEHOLDER = "Ask a general health question…";
export const PRIVACY_HINT =
  "Please don't include names, ID numbers, addresses, or other personal details.";
export const LOADING_TEXT = "Waiting for a reply…";
export const CHATS_NOT_SAVED =
  "Chats are not saved. Starting a new chat clears this conversation.";

// docs/06_UI_UX_Design.md §4 service-error wording (also the API's 500 message).
export const SERVICE_ERROR =
  "Sorry, the assistant is temporarily unavailable. Please try again later. " +
  "If this is urgent, contact emergency services or a healthcare professional.";

// Headings for the error states. The body is always SERVICE_ERROR, which includes the
// emergency line; no server or exception text is ever shown.
export const ERROR_HEADINGS = {
  unreachable: "HealthChat AI could not be reached",
  unavailable: "HealthChat AI is unavailable",
  unreadable: "This reply could not be shown",
  unexpected: "Something went wrong",
} as const;
export type ErrorState = keyof typeof ERROR_HEADINGS;

// API_CONTRACT v0.3 "Frontend obligations": labels that never suggest clinical review.
export const MOCK_LABEL = "Mock response";
export const SAFETY_LABEL = "Automated safety message (prototype)";
export const CURATED_LABEL = "Educational content: owner reviewed, not clinically reviewed";
export const SOURCES_HEADING = "Sources";

// The approved safe_fallback reply (D-20, templates-0.1), shown when the server sends
// a kind or content_source this client does not know ("treat as safe_fallback").
// Must match docs/API_CONTRACT.md exactly; checked by src/api/contract.test.ts.
export const SAFE_FALLBACK_REPLY = {
  title: "HealthChat AI can't answer this safely",
  paragraphs: [
    "I couldn't find enough reliable information to answer this safely. Please rephrase " +
      "your question or consult a qualified healthcare professional.",
    "If you think you may be experiencing an emergency, contact local emergency services immediately.",
  ],
} as const;

// Same limits as the backend (config.MAX_INPUT_CHARS, safety.SCAN_LIMIT_CHARS).
export const MAX_INPUT_CHARS = 1_000;
export const HARD_LIMIT_CHARS = 20_000;

// Same examples as the Streamlit UI; chosen not to copy evaluation-set questions.
export const SUGGESTED_QUESTIONS = [
  "Why is staying hydrated important?",
  "What is good sleep hygiene?",
  "What does a balanced diet include?",
  "How does regular exercise support health?",
] as const;

export const FEATURES = [
  {
    title: "General information",
    text: "Plain-language explanations of common health topics.",
  },
  {
    title: "Safety checks first",
    text: "Emergency and personal-advice questions are handled before anything else.",
  },
  {
    title: "Honest about limits",
    text: "When no reviewed content fits, HealthChat AI says so instead of guessing.",
  },
] as const;
