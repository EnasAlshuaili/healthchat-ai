# UI/UX Design Specification
## QueryMate: AI Healthcare Question Answering Chatbot

- **Version:** 1.0
- **Status:** Proposed interface specification

## 1. Design principles
- Calm, clear, and trustworthy visual language.
- Readable typography and accessible contrast.
- Distinguish user messages from chatbot responses.
- Keep the medical disclaimer visible.
- Make uncertainty and emergency guidance prominent.
- Avoid visual elements that imply the chatbot is a real doctor or a clinically approved diagnostic service.

## 2. Main screen layout
### Header
- Product name: QueryMate.
- Subtitle: “AI-powered general healthcare information.”
- Optional status label: “Educational prototype.”

### Main chat area
- Welcome message and example questions.
- User and assistant message bubbles.
- Loading indicator while processing.
- A safe fallback if the model cannot answer confidently.
- Optional small “Retrieved information” note if supported by implementation.

### Input area
- Text input with placeholder: “Ask a general healthcare question…”
- Send button.
- Clear conversation action.
- Do not encourage users to enter full names, IDs, addresses, or other unnecessary personal information.

### Disclaimer
Display near the chat, not only in a separate page:
“QueryMate provides general health information and is not a substitute for professional medical advice, diagnosis, or treatment. If you think you may be experiencing an emergency, contact local emergency services immediately.”

## 3. Key user journeys
### Journey A — General health question
1. User opens the chat.
2. Reads disclaimer.
3. Enters a question.
4. Sees processing state.
5. Receives relevant answer or fallback.
6. Can ask a follow-up or reset the chat.

### Journey B — Uncertain question
1. User enters an unsupported or ambiguous question.
2. Retrieval score is below the validated threshold.
3. System asks for clarification or provides a safe fallback.
4. It does not return a weakly related answer as if it were reliable.

### Journey C — Potential emergency
1. User describes a potentially life-threatening symptom.
2. Safety logic takes priority over normal retrieval.
3. Interface displays concise urgent guidance.
4. The system does not delay the user with a long AI-generated explanation.

## 4. Suggested copy
### Welcome
“Hello! I’m QueryMate, an AI assistant for general healthcare information. What would you like to learn about today?”

### Loading
“Looking for relevant information…”

### Low confidence
“I couldn’t find enough reliable information to answer this safely. Please rephrase your question or consult a qualified healthcare professional.”

### Service error
“Sorry, the assistant is temporarily unavailable. Please try again later. If this is urgent, contact emergency services or a healthcare professional.”

## 5. Accessibility requirements
- Inputs and buttons have clear labels.
- Keyboard navigation is supported.
- Text contrast is readable.
- Error messages are descriptive.
- Do not use color alone to communicate an emergency or error.
- Long responses remain readable and are broken into short paragraphs or bullets.

## 6. Responsive behavior
The chat should remain usable on desktop and mobile widths. The input should remain easy to reach, and long answers should not overflow the viewport.

## 7. UI states to design
- Initial/welcome state.
- User question submitted.
- Loading.
- Successful answer.
- Low-confidence fallback.
- Emergency guidance.
- Backend/model error.
- Empty-input validation.
- Cleared conversation.

## 8. Proposed visual direction
Use a restrained healthcare-inspired palette, a clean sans-serif font, ample whitespace, rounded but not overly playful message bubbles, and clear hierarchy. Avoid medical claims in branding such as “doctor-approved” unless formally substantiated.

## 9. Usability test questions
- Can users identify where to type a question?
- Do users understand the chatbot is not a doctor?
- Can users distinguish a general answer from emergency guidance?
- Do users understand a low-confidence fallback?
- Can users clear a conversation?
