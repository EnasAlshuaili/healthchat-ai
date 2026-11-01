# HealthChat AI API Contract

**Contract version: v0.3 (approved by the project owner, 2026-10-31; D-21). Implemented in `curated_single_topic` mode** by `src/querymate/api/`, which delegates every question to `src/querymate/pipeline.py` (tests: `tests/test_api.py`, `tests/test_pipeline.py`, `tests/test_knowledge.py`). v0.2 (`router_only`) and v0.1 (`mock`) are superseded; see [Changes from v0.2](#changes-from-v02) and [Superseded v0.1](#superseded-v01).

> **Educational prototype.** Every reply is fixed server-side text: a fixed safety or input-check template, or an owner-reviewed curated answer with its sources. Curated answers are owner review of educational content only: they have **not** been clinically reviewed or clinically validated. The API never returns answers from the healthcare dataset (D-01), never calls an LLM or external AI service (D-06), and must not claim clinical validation or medical accuracy (D-11). The Safety & Scope Router is a keyword-rule prototype (D-17); its routes are not clinical triage, are not comprehensive, and are not clinically validated.

Related: `docs/DECISIONS.md` (D-01, D-02, D-06, D-07, D-08, D-11, D-14, D-17, D-18, D-19, D-20, D-21), `curated/topic_content.json`, `docs/STEP3_DECISION_REVIEW.md`, `docs/SAFETY_ROUTER.md`, `docs/06_UI_UX_Design.md`.

## Modes

The response shape is the same in every mode. What changes is which components are connected and which `kind` values the server can produce. Each new mode needs its own owner-approved decision.

| Mode (`/api/health` `mode`) | Status | Server behaviour | Possible `kind` values |
|---|---|---|---|
| `mock` | v0.1, **superseded** (D-19) | The question is not analysed. Only empty and over-length checks run. | `mock_answer`, `invalid_input` |
| `router_only` | v0.2, **superseded** (D-21) | The Safety & Scope Router (v0.1.1) decides the route. Non-`PROCEED` routes get fixed safety or input-check templates. `PROCEED` gets the mock placeholder. | all except `curated_answer` |
| `curated_single_topic` | v0.3, **approved (D-21) and implemented** | The router decides the route exactly as in v0.2. Non-`PROCEED` routes get the same templates. After `PROCEED` only, an exact lookup finds an owner-reviewed curated entry. One topic exists (hydration). No match gets `safe_fallback`. The topic matcher is **not** connected. | all except `mock_answer` |
| matcher connected | **Not approved** | After `PROCEED`, the topic matcher would run with an owner-approved configuration and threshold. None is chosen (D-15, D-20). | all |

Each further curated topic needs owner review of its answer and source mapping before it can be displayed (D-01, D-21).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/chat` | Submit one question, receive one reply |
| `GET` | `/api/health` | Liveness, mode, and connected component versions |

The API is **stateless**. Each request carries one question. There is no conversation history, session, cookie, or authentication, and nothing is stored on the server (FR-14).

## `POST /api/chat`

### Request

Headers: `Content-Type: application/json`.

```json
{ "question": "Why is staying hydrated important?" }
```

| Field | Type | Required | Rules |
|---|---|---|---|
| `question` | string | yes | Must be a JSON string. No length limit in the schema (see the next section). |

Unknown fields are rejected (`422 invalid_request`).

### Input validation

Checks run in this order. Only transport and schema problems are HTTP errors. Problems with the question itself return `200` with a displayable reply.

| # | Condition | Result |
|---|---|---|
| 1 | Body larger than **131,072 bytes** (128 KiB) | `413 payload_too_large` |
| 2 | `Content-Type` is not `application/json` | `415 unsupported_media_type` |
| 3 | Body is not valid JSON, `question` is missing or not a string, or there are unknown fields | `422 invalid_request` |
| 4 | `question` is empty or whitespace only | `200`, `kind: "invalid_input"`, empty-question reply |
| 5 | `question` is longer than **1,000 characters** after whitespace normalisation (`config.MAX_INPUT_CHARS`) | The router scans the first **20,000 characters** for crisis and emergency signals (`SCAN_LIMIT_CHARS`, D-17) and returns `crisis` or `emergency` if one fires; otherwise `kind: "invalid_input"` with the over-length reply. (`mock` mode: always the over-length reply.) |

Why there is no schema-level 1,000-character limit: a schema limit would reject long messages before the router's crisis and emergency scan could run (D-17). The 128 KiB body limit covers 20,000 characters even in the worst case (4-byte UTF-8 characters or 6-byte JSON escapes) plus JSON overhead.

Rows 4 and 5 are decided by the router, which returns `INVALID_INPUT` for both. The reply is chosen by reason code:

| Router reason codes include | Reply |
|---|---|
| `input:too_long` | Over-length reply |
| `input:empty` or `input:not_text` | Empty-question reply |
| neither | Fail closed: safe-fallback reply |

### Response: `200 OK`

Returned for every outcome the server decides, including `invalid_input` and fail-closed replies.

```json
{
  "api_version": "0.3",
  "request_id": "6f1c2a9e-0b7d-4c1e-9a43-2f0f8b6d1c55",
  "kind": "curated_answer",
  "content_source": "curated_owner_reviewed",
  "message": {
    "title": "Why staying hydrated matters",
    "paragraphs": [
      "Water helps your body keep a normal temperature, lubricates and cushions your joints, and helps get rid of waste through urination, sweating, and bowel movements.",
      "Not getting enough fluid can lead to dehydration.",
      "You may need more fluid in hot weather, during physical activity, or when you are ill. Recommended daily water intake varies, for example by age, sex, and activity level.",
      "This is general educational content reviewed by the project owner. It has not been clinically reviewed or clinically validated. For personal advice, consult a qualified healthcare professional. If you think you may be experiencing an emergency, contact local emergency services immediately."
    ]
  },
  "sources": [
    { "title": "About Water and Healthier Drinks", "organization": "Centers for Disease Control and Prevention (CDC)", "url": "https://www.cdc.gov/healthy-weight-growth/water-healthy-drinks/" },
    { "title": "Water, drinks and hydration", "organization": "NHS", "url": "https://www.nhs.uk/Live-well/eat-well/food-guidelines-and-food-labels/water-drinks-nutrition/" },
    { "title": "Dehydration", "organization": "NHS", "url": "https://www.nhs.uk/conditions/dehydration/" }
  ],
  "review_status": "owner_reviewed",
  "is_mock": false,
  "abstained": false,
  "abstain_reason": null,
  "disclaimer": "HealthChat AI provides general health information and is not a substitute for professional medical advice, diagnosis, or treatment. If you think you may be experiencing an emergency, contact local emergency services immediately.",
  "versions": { "router": "0.1.1", "matcher": null, "content": "templates-0.1", "knowledge": "0.1.0" }
}
```

| Field | Type | Rules |
|---|---|---|
| `api_version` | string | `"0.3"` for this contract |
| `request_id` | string (UUID4) | New for every request; also sent as the `X-Request-ID` header. Not linked to any stored data. |
| `kind` | enum | See [`kind` values](#kind-values) |
| `content_source` | enum | `"curated_owner_reviewed"`, `"mock_placeholder"`, `"safety_template"`, or `"input_check"`; determined by `kind` (next table). `"reviewed_content"` stays reserved and must not be produced. |
| `message.title` | string | Fixed server text ([Reply templates](#reply-templates) or [Curated answers](#curated-answers)) |
| `message.paragraphs` | string[] | 1–5 fixed server paragraphs. Never contains the user's question, dataset text, or generated text. |
| `sources` | object[] | Non-empty **if and only if** `kind` is `curated_answer`; otherwise `[]`. Each item has exactly `title`, `organization`, and an `https` `url`. |
| `review_status` | enum or null | `"owner_reviewed"` **if and only if** `kind` is `curated_answer`; otherwise `null`. This means owner review of educational content, never clinical review. |
| `is_mock` | boolean | **`true` if and only if `kind` is `mock_answer`.** The response model must make any other pairing impossible. |
| `abstained` | boolean | Always `false` (these fields belong to the matcher, which is not connected). A curated lookup with no match is not reported here. |
| `abstain_reason` | enum or null | Always `null`. Reserved values: `no_overlap`, `below_min_score`, `below_min_margin`, `matcher_unavailable` |
| `disclaimer` | string | Exactly the disclaimer in `06_UI_UX_Design.md` §2 |
| `versions.router` | string or null | See [`versions.router` rule](#versionsrouter-rule) |
| `versions.matcher` | string or null | Always `null` (the matcher is not connected) |
| `versions.content` | string | Version of the fixed template set: `"templates-0.1"` |
| `versions.knowledge` | string or null | `"0.1.0"` **if and only if** `kind` is `curated_answer`; otherwise `null` |

### `versions.router` rule

In a `/api/chat` response, `versions.router` is the router version (`"0.1.1"`) **only when the router actually ran and produced the routing decision that this reply is based on**. It is `null` when:

- the router was not called (for example, a pipeline failure before routing);
- the router call raised an exception;
- the router returned its own internal-error fallback (reason code `router:error`), because no routing rules were applied; or
- the reply is a fail-closed safe fallback for any other internal error, because the reply is then not based on a routing decision.

Every one of these cases returns the approved safe-fallback reply (`kind: "safe_fallback"`, `200`) without technical details.

A `safe_fallback` reply because a `PROCEED` question has no curated entry is **not** a failure: the router did decide, so `versions.router` stays `"0.1.1"`. If the curated knowledge cannot be loaded or an entry may not be displayed, the reply fails closed and `versions.router` is `null`.

### `kind` values

| `kind` | `content_source` | `is_mock` | Produced when | Router route (internal) |
|---|---|---|---|---|
| `curated_answer` | `curated_owner_reviewed` | `false` | Router returns `PROCEED` and the question exactly matches an owner-reviewed entry | `proceed` |
| `mock_answer` | `mock_placeholder` | `true` | **Not produced since v0.3.** The template stays on record. | none |
| `invalid_input` | `input_check` | `false` | Router returns `INVALID_INPUT` (empty or over-length, no urgent signal) | `invalid_input` |
| `emergency` | `safety_template` | `false` | Router: possible emergency | `emergency_guidance` |
| `crisis` | `safety_template` | `false` | Router: possible self-harm, overdose, or immediate danger | `crisis_guidance` |
| `decline_diagnosis` | `safety_template` | `false` | Router: diagnosis request | `decline_diagnosis_refer` |
| `decline_dosage` | `safety_template` | `false` | Router: dosage or medicine-choice request | `decline_dosage_refer` |
| `out_of_scope` | `safety_template` | `false` | Router: no health vocabulary, animal or veterinary, or finance/admin question | `out_of_scope_fallback` |
| `safe_fallback` | `safety_template` | `false` | Router: `SAFE_FALLBACK`; `PROCEED` with no curated entry (D-02); any router, knowledge, or pipeline error (fail closed) | `safe_fallback`, `proceed`, or none |

The router's rules and priority order are unchanged (D-17, v0.1.1): `INVALID_INPUT`, `CRISIS`, `EMERGENCY`, `DOSAGE`, `DIAGNOSIS`, `SAFE_FALLBACK`, `OUT_OF_SCOPE`, `PROCEED`, with long-input crisis and emergency signals checked before the length rejection.

### Reply templates

Approved wording (D-20, `templates-0.1`). Each paragraph below is one entry in `message.paragraphs`, in order. Text must be used exactly as written.

**`emergency`**: title "Possible emergency"

1. If you or someone else may be in immediate danger, contact local emergency services immediately.
2. HealthChat AI is an educational prototype and cannot provide crisis intervention or assess immediate safety. Do not wait for a response from HealthChat AI if urgent help may be needed.

**`crisis`**: title "Please get help now"

1. If you or someone else may be in immediate danger, contact local emergency services immediately.
2. HealthChat AI is an educational prototype and cannot provide crisis intervention or assess immediate safety. Do not wait for a response from HealthChat AI if urgent help may be needed.
3. If you are thinking about harming yourself, please reach out to someone you trust who can support you now. If you or someone else may have taken too much of a medicine or other substance, seek emergency help immediately. If possible, stay with someone you trust while getting help.

**`decline_diagnosis`**: title "HealthChat AI can't diagnose"

1. HealthChat AI is an educational prototype and cannot diagnose conditions or say what may be causing symptoms.
2. Please talk to a doctor or another qualified healthcare professional, who can assess your situation. If symptoms are severe, getting worse, or worrying you, seek professional care.
3. If you think you may be experiencing an emergency, contact local emergency services immediately.

**`decline_dosage`**: title "HealthChat AI can't advise on medicines or doses"

1. HealthChat AI is an educational prototype and cannot recommend medicines, suggest doses, or advise on starting, stopping, changing, or combining medicines.
2. For questions about medicines, please ask a pharmacist, your prescriber, or another qualified healthcare professional, or check the official information leaflet that comes with the medicine.
3. If you think you may be experiencing an emergency, contact local emergency services immediately.

**`out_of_scope`**: title "This question is outside what HealthChat AI covers"

1. HealthChat AI only provides general educational information about human health topics, so it can't help with this question.
2. Please try a general health question, or ask a suitable professional or service about this topic.
3. If you think you may be experiencing an emergency, contact local emergency services immediately.

**`safe_fallback`**: title "HealthChat AI can't answer this safely"

1. I couldn't find enough reliable information to answer this safely. Please rephrase your question or consult a qualified healthcare professional.
2. If you think you may be experiencing an emergency, contact local emergency services immediately.

**`invalid_input`, empty question**: title "Please enter a question."

1. Type a general health question, then send it.

**`invalid_input`, over-length question**: title "Your question is too long."

1. Please shorten it to 1,000 characters or fewer.
2. If you think you may be experiencing an emergency, contact local emergency services immediately.

**`mock_answer`**: title "Mock response: answers are not available yet"

1. This is a placeholder. HealthChat AI's answer system is not connected, so your question has not been checked or answered.
2. For health concerns, please consult a qualified healthcare professional. If you think you may be experiencing an emergency, contact local emergency services immediately.

Caveats recorded with the approval (D-20): `decline_diagnosis` does not decide whether "prompt" evaluation is required; `decline_dosage` deliberately does not tell users to keep taking or stop a medicine; "human health" in `out_of_scope` settles reply wording only, not evaluation conventions; the `safe_fallback` wording (06 §4) fits rule-override and certainty-demand cases imperfectly.

### Fail-safe rules

- The router runs before anything else. The curated lookup runs **only** after `PROCEED`. The topic matcher and the TF-IDF retrieval baseline are never called.
- Every non-`PROCEED` route returns its fixed template. No route returns dataset text.
- `PROCEED` with no curated entry returns the `safe_fallback` reply. Nothing is guessed or generated (D-02).
- Any router error, undefined route, unknown reason code, unexpected `INVALID_INPUT` reason, knowledge failure, or pipeline exception returns the `safe_fallback` reply with `versions.router: null`. Failures never lead to `mock_answer` or `curated_answer`.
- If the matcher is connected in a future mode, it runs **only** after `PROCEED` (`match_after_precheck`, D-15(d), D-17), never overrides a route, and a match is **not** permission to display content.
- Unexpected failures outside the pipeline still return `500 internal_error` ([Structured errors](#structured-errors)).

### Curated answers

Approved by the project owner on 2026-10-31 (D-21). The source of truth is `curated/topic_content.json` (entry `KN-0001`, knowledge version `0.1.0`), which also records the evidence for each statement, and page review dates, including the NHS water page's passed review date (next review due 2026-05-17). Owner review of educational content only: **not** clinical review or medical validation.

Only an `owner_reviewed` entry can be displayed. A question matches only if, after normalising case, punctuation, and spacing, it equals an approved question:

- Why is staying hydrated important?
- Why is hydration important?
- Why is it important to stay hydrated?
- Why is staying hydrated important for the body?
- Why does the body need water?
- Why do we need to drink water?

Anything else gets `safe_fallback`, including rewordings the router allows. This is deliberate: the general answer must not be applied to questions about babies, pregnancy, symptoms, or combined questions. The answer text is shown in the [`200 OK` example](#response-200-ok).

### Diagnostics (developer only, not implemented)

Router reason codes are **not** in normal responses. When the server is started with `QUERYMATE_API_DIAGNOSTICS=true`, the response may include:

```json
"diagnostics": { "route": "proceed", "reason_codes": ["scope:health_vocabulary_no_risk_rule"] }
```

Diagnostics contain fixed rule names only, never user text or dataset text. They are off by default, and the frontend must not show them to users.

## `GET /api/health`

```json
{ "status": "ok", "api_version": "0.3", "mode": "curated_single_topic", "versions": { "router": "0.1.1", "matcher": null, "content": "templates-0.1", "knowledge": "0.1.0" } }
```

- `mode` is `"curated_single_topic"` for this contract.
- `versions` reports the **configured, connected** components, not the execution of the router for any request. `versions.router` is `"0.1.1"`, `versions.matcher` is `null`, and `versions.knowledge` is `"0.1.0"`, or `null` if the curated knowledge could not be loaded.
- The health check runs no question through the router and must not load the dataset or the retrieval index.

## Structured errors

Every non-`200` response uses one envelope:

```json
{ "error": { "code": "invalid_request", "message": "The request could not be processed. Please send a JSON body with a text \"question\" field.", "request_id": "6f1c2a9e-0b7d-4c1e-9a43-2f0f8b6d1c55" } }
```

| Status | `code` | When |
|---|---|---|
| 404 | `not_found` | Unknown path |
| 405 | `method_not_allowed` | Wrong HTTP method |
| 413 | `payload_too_large` | Body over 128 KiB |
| 415 | `unsupported_media_type` | Not `application/json` |
| 422 | `invalid_request` | Malformed JSON, wrong field type, missing or unknown fields |
| 500 | `internal_error` | Unexpected server error outside the pipeline |

Rules:

- `message` is fixed text chosen by the server. It **never echoes request content**. FastAPI's default validation error, which includes the submitted `input`, must be replaced.
- No stack traces, exception text, file paths, or library versions appear in responses (TC-11).
- The `500` message uses the service-error wording from `06_UI_UX_Design.md` §4 and includes the emergency line: "Sorry, the assistant is temporarily unavailable. Please try again later. If this is urgent, contact emergency services or a healthcare professional."

## Privacy requirements

- **No storage.** Questions and replies are not written to disk, databases, caches, or logs (FR-14, BR-08).
- **No content logging.** Request bodies, questions, replies, and router reason codes for a request are never logged. Exceptions are logged without request content. The Uvicorn access log is off (it records client addresses and query strings).
- **No external calls.** The API sends nothing to external services, including LLM, analytics, telemetry, or font providers (D-06).
- Responses send `Cache-Control: no-store`.
- No cookies, sessions, authentication, or user identifiers. `request_id` is random and per-request.

## Content rules

- Reply text comes only from the fixed [reply templates](#reply-templates) and owner-reviewed [curated answers](#curated-answers). Neither contains diagnoses, treatments, medicine names, or doses.
- Emergency and crisis templates use generic wording with no phone numbers or named helplines until location-specific contacts are verified (D-07).
- Dataset answers are never returned (D-01). The retrieval baseline is not part of the chat path. Curated topic examples remain `pending_owner_review` and are not answer content.
- Neither the API nor the frontend may describe replies as verified, medically approved, clinically reviewed, or clinically validated. Saying that a reply has **not** been clinically reviewed is required for curated answers.

## Frontend obligations

- Render `message`, `disclaimer`, and error messages as **plain text**. Never use `dangerouslySetInnerHTML` or render Markdown/HTML from the API.
- Show a visible "Mock response" label **only** when `is_mock` is `true`.
- For `content_source: "safety_template"`, show a label such as "Automated safety message (prototype)". The label must not suggest clinical review or validation.
- For `content_source: "curated_owner_reviewed"`, show the label "Educational content: owner reviewed, not clinically reviewed".
- Show `sources` only for a valid `curated_answer`, as plain text with `https` links. Never show sources on any other reply.
- Show `emergency` and `crisis` replies prominently, with an icon and a text heading (never colour alone), announced to screen readers as an alert.
- Treat any unknown `kind` or `content_source` as `safe_fallback`.
- Keep the disclaimer and the safety notice visible in the chat view.
- Do **not** implement safety logic. The server decides every outcome.
- Do **not** hard-block messages over 1,000 characters. Show a soft warning and let the server respond. A hard client limit of 20,000 characters matches the router's scan limit.
- Show loading, empty, error, and network-failure states. Network-failure text includes the emergency line.

## Local-only development

| Service | Address | Notes |
|---|---|---|
| FastAPI | `http://127.0.0.1:8000` | Bound to localhost only |
| Vite dev server (React) | `http://127.0.0.1:5173` | Forwards `/api/*` to FastAPI through the dev proxy |
| Streamlit reference UI | `http://localhost:8501` | Unchanged (D-18) |

- The browser talks only to the Vite dev server, so requests are same-origin and **CORS stays disabled**. If CORS is ever needed, it allows `http://localhost:5173` only, never `*`.
- No public deployment or network exposure until dataset licence and permitted use are established (D-08).

## Contract tests required for v0.3

- Each validation row returns the documented status, `kind`, and reply, including the reason-code selection for `INVALID_INPUT`.
- Each router route maps to its `kind`, `content_source`, `is_mock` value, and exact template text.
- `is_mock` is `true` exactly when `kind` is `mock_answer`.
- `sources`, `review_status`, and `versions.knowledge` are set exactly when `kind` is `curated_answer`.
- `versions.router` is `"0.1.1"` for router decisions and `null` for every fail-closed case (router not called, router exception, `router:error`, knowledge failure, pipeline exception).
- The curated lookup runs only after `PROCEED`, and safety routes win over hydration wording.
- The topic matcher and retrieval baseline are never called, and no dataset text appears in any response.
- No response contains the submitted question (test with a unique marker string).
- Error responses use the envelope and never contain the submitted text.
- `Cache-Control: no-store` and `X-Request-ID` headers are present.
- `/api/health` reports `mode: "curated_single_topic"` and the connected versions without loading the dataset or retrieval index.
- The API package imports no retrieval or dataset modules.

## Versioning

Breaking changes to field names, types, or meanings increase `api_version` and require an update to this document and to `docs/DECISIONS.md`. Clients must treat unknown `kind` or `content_source` values as `safe_fallback`.

### Changes from v0.2

| Item | v0.2 | v0.3 |
|---|---|---|
| `api_version` | `"0.2"` | `"0.3"` |
| `PROCEED` with a curated match | `mock_answer` | New `kind` `curated_answer` |
| `PROCEED` with no curated match | `mock_answer` | `safe_fallback` with `versions.router: "0.1.1"` |
| `mock_answer` | Produced | Not produced; template kept on record |
| `content_source` | — | Adds `curated_owner_reviewed`; `reviewed_content` stays reserved |
| `sources`, `review_status` | — | New, required |
| `versions.knowledge` | — | New, required |
| Health `mode` | `"router_only"` | `"curated_single_topic"` |

Safety and input-check templates, router rules, and `templates-0.1` are unchanged.

### Changes from v0.1

| Item | v0.1 | v0.2 |
|---|---|---|
| `api_version` | `"0.1"` | `"0.2"` |
| `is_mock` | Literal `true` | `true` if and only if `kind` is `mock_answer` |
| `content_source` | — | New, required |
| `versions.router` | `null` | `"0.1.1"` when the router produced the decision; `null` otherwise |
| `versions.content` | `"mock"` | `"templates-0.1"` |
| Health `mode` | `"mock"` | `"router_only"` |
| Health `versions` | Components connected (none) | Components connected (router `"0.1.1"`) |
| Phase names | Phases A, B, C | Modes `mock`, `router_only`, matcher connected (renamed to avoid confusion with Step 3's implementation phases) |
| Reply wording | Mock and input checks only | Approved templates for every `kind` (D-20) |
| "Mock response" label | Whenever `is_mock` is `true` (always) | Only for `mock_answer`; safety templates get their own label |

## Superseded v0.1

Before v0.2 was implemented, `src/querymate/api/` served v0.1 in `mock` mode: `api_version: "0.1"`, `is_mock: true` on every reply, no `content_source` field, `versions: { "router": null, "matcher": null, "content": "mock" }`, health `mode: "mock"`, and only the `mock_answer` and `invalid_input` kinds. The question is not analysed. All other rules in this document (validation order, body limit, errors, privacy, local-only development) also applied to v0.1. This section summarises v0.1; its full text is not kept separately (this file has not been committed).
