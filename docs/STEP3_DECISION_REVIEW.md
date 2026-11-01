# Step 3 Decision Review: Router-Only Integration

**Status: all items approved by the owner (2026-10-20) and recorded as decision D-20.** `docs/API_CONTRACT.md` is updated to v0.2. **Phases A, B, and C are implemented** (the pipeline, the API serving contract v0.2 in `router_only` mode, and the React frontend calling the API through the Vite dev proxy).

> QueryMate is an educational prototype. The Safety & Scope Router is a keyword-rule prototype (D-17): it is not clinical triage, not comprehensive, and not clinically validated. Passing tests does not show that any reply is medically accurate or safe.

## 1. Status summary

| # | Item | Status |
|---|---|---|
| 1 | Emergency reply wording (section 2) | **Approved**, word for word, including the paragraph split |
| 2 | Crisis reply structure: approved emergency text first, unchanged, then a separate crisis-support paragraph | **Approved** |
| 2a | Crisis-support paragraph wording | **Approved**, word for word (section 3) |
| 3 | Router-only integration: topic matcher not connected; no threshold chosen or tuned | **Approved** |
| 4 | Six reply titles (section 4) | **Approved** |
| 5 | Diagnosis, dosage, out-of-scope, and safe-fallback replies (5.1 to 5.4), with their limitations and caveats retained | **Approved** |
| 6 | API Contract v0.2, including `is_mock`, `content_source`, and the `versions.router` rule (section 7) | **Approved** |
| 6a | `versions.router` is `null` when the router was not called, raised an exception, or returned `router:error` | **Approved** |
| 6b | `GET /api/health` reports connected component versions (`mode: "router_only"`, `versions.router: "0.1.1"`) | **Approved** |
| 7 | `INVALID_INPUT` replies: empty and over-length messages differ (section 5.5) | **Reviewed: confirmed different**; selection rule documented |
| 8 | Update `docs/API_CONTRACT.md` to v0.2 and record D-20 | **Done** (2026-10-20) |

**Implementation status:** phases A, B, and C are done (section 9). The router must not be connected for some routes and not others: every route, including crisis, uses its approved reply from the first release (D-14).

## 2. Approved: emergency reply (route `EMERGENCY`, kind `emergency`)

Title (**approved**): Possible emergency

Body text (**approved word for word**):

> If you or someone else may be in immediate danger, contact local emergency services immediately. QueryMate is an educational prototype and cannot provide crisis intervention or assess immediate safety. Do not wait for a response from QueryMate if urgent help may be needed.

Paragraph split (**approved**, formatting only, no wording change): paragraph 1 is the first sentence; paragraph 2 is the remaining two sentences.

Checks against existing policy: emergency direction first (07 §4); generic wording with no phone numbers (D-07); covers reports about another person; no questions about intent; does not claim to assess safety.

## 3. Crisis reply (route `CRISIS`, kind `crisis`)

Title (**approved**): Please get help now

Structure (**approved**): the approved emergency reply from section 2 (both paragraphs, unchanged) comes first, followed by **one separate crisis-support paragraph** as the third paragraph.

Crisis-support paragraph (**approved word for word**, 2026-10-20):

> If you are thinking about harming yourself, please reach out to someone you trust who can support you now. If you or someone else may have taken too much of a medicine or other substance, seek emergency help immediately. If possible, stay with someone you trust while getting help.

Checks against the requirements (D-07, D-14):

- It names no helpline or phone number. Location-specific contacts remain an open item.
- It does not ask about intent and comes after the emergency direction.
- It covers reports about another person ("you or someone else may have taken too much"; V024 convention).
- It provides generic crisis support (a trusted person who can support you now; emergency help for a possible overdose), which D-14 requires in addition to the emergency direction.

This wording supersedes the earlier assistant proposal, which was never approved. Its approval resolves the "wording of generic crisis support" part of the D-14 open item.

## 4. Approved reply titles

| Kind | Title |
|---|---|
| `emergency` | Possible emergency |
| `crisis` | Please get help now |
| `decline_diagnosis` | QueryMate can't diagnose |
| `decline_dosage` | QueryMate can't advise on medicines or doses |
| `out_of_scope` | This question is outside what QueryMate covers |
| `safe_fallback` | QueryMate can't answer this safely |

## 5. Approved replies (with limitations and caveats retained)

All replies are fixed text. None depends on the question, repeats it, gives medical advice, or uses dataset text. Each reply in 5.1 to 5.4 ends with the generic emergency line (D-07, the same sentence used in the disclaimer and mock reply): "If you think you may be experiencing an emergency, contact local emergency services immediately."

### 5.1 Diagnosis request (route `DIAGNOSIS`, kind `decline_diagnosis`): approved

Basis: ST-05, FR-09, 07 §2 principle 3 and §5 ("no definitive diagnosis"; "if symptoms are severe, worsening, or concerning, recommend professional evaluation").

> QueryMate is an educational prototype and cannot diagnose conditions or say what may be causing symptoms.
>
> Please talk to a doctor or another qualified healthcare professional, who can assess your situation. If symptoms are severe, getting worse, or worrying you, seek professional care.
>
> If you think you may be experiencing an emergency, contact local emergency services immediately.

Caveat (retained): the reply says "seek professional care" without "promptly". Whether "prompt" evaluation is required remains an unresolved policy choice (`eval/README.md`); this approval does not decide it.

### 5.2 Medication or dosage request (route `DOSAGE`, kind `decline_dosage`): approved

Basis: ST-06, ST-07, 07 §2 principle 4 and §5 (no individual dose; do not advise stopping prescribed treatment; refer to a clinician, pharmacist, prescriber, or official product label).

> QueryMate is an educational prototype and cannot recommend medicines, suggest doses, or advise on starting, stopping, changing, or combining medicines.
>
> For questions about medicines, please ask a pharmacist, your prescriber, or another qualified healthcare professional, or check the official information leaflet that comes with the medicine.
>
> If you think you may be experiencing an emergency, contact local emergency services immediately.

Caveat (retained): the reply deliberately does **not** say "do not stop your medicine". That would itself be advice about the user's treatment. It only says QueryMate cannot advise and names who can.

### 5.3 Out of scope (route `OUT_OF_SCOPE`, kind `out_of_scope`): approved

Basis: TC-05/TC-06; `eval/README.md` (`out_of_scope_fallback` passes with a scope explanation or the general safe fallback). The router sends three kinds of question here: no health vocabulary, animal or veterinary questions (D-17), and finance/admin questions (v0.1.1). Because replies never depend on the question, one generic template covers all three.

> QueryMate only provides general educational information about human health topics, so it can't help with this question.
>
> Please try a general health question, or ask a suitable professional or service about this topic.
>
> If you think you may be experiencing an emergency, contact local emergency services immediately.

Caveat (retained): "human health" reflects D-17 (veterinary questions route here). "Human health only" is listed as an unresolved policy choice in `eval/README.md`. This approval settles the reply wording only; it does not change evaluation labels or grading conventions.

### 5.4 Safe fallback (route `SAFE_FALLBACK`, kind `safe_fallback`): approved

Basis: D-02; FR-07; the low-confidence wording in **`docs/06_UI_UX_Design.md` §4** (reused verbatim as the first paragraph). This reply is also the fail-closed reply: any router error, undefined route, unknown reason code, or pipeline exception returns it (D-17, R-10).

> I couldn't find enough reliable information to answer this safely. Please rephrase your question or consult a qualified healthcare professional.
>
> If you think you may be experiencing an emergency, contact local emergency services immediately.

Caveat (retained): the router also uses `SAFE_FALLBACK` for attempts to override safety rules, "act as a doctor" requests, and demands for certainty. The 06 wording ("couldn't find enough reliable information") fits those cases imperfectly but does not mislead. A separate wording for them would be a new decision.

### 5.5 Unchanged replies (reviewed)

- `mock_answer` (route `PROCEED`): the existing fixed mock placeholder. With the matcher not connected, every `PROCEED` question gets it.
- `invalid_input` (route `INVALID_INPUT`): two **different** existing replies, confirmed in `src/querymate/api/replies.py`:

| Case | Title | Paragraphs |
|---|---|---|
| Empty or whitespace-only | Please enter a question. | "Type a general health question, then send it." |
| Over-length (> 1,000 characters, no crisis or emergency signal) | Your question is too long. | "Please shorten it to 1,000 characters or fewer." and the generic emergency line |

**Selection rule with the router connected.** The router returns `INVALID_INPUT` for both cases and distinguishes them only by reason code. If the reason codes include `input:too_long`, the over-length reply is used. If they include `input:empty` or `input:not_text`, the empty reply is used. Any other `INVALID_INPUT` decision fails closed to the safe fallback (5.4). Over-length messages that contain crisis or emergency signals never reach this rule: the router returns `CRISIS` or `EMERGENCY` for them (D-17).

## 6. Route-to-reply mapping (router-only integration)

| Router route | `kind` | Reply | `is_mock` | `content_source` |
|---|---|---|---|---|
| `CRISIS` | `crisis` | Section 3 (approved) | false | `safety_template` |
| `EMERGENCY` | `emergency` | Section 2 (approved) | false | `safety_template` |
| `DOSAGE` | `decline_dosage` | 5.2 (approved) | false | `safety_template` |
| `DIAGNOSIS` | `decline_diagnosis` | 5.1 (approved) | false | `safety_template` |
| `SAFE_FALLBACK`, router error, pipeline error | `safe_fallback` | 5.4 (approved) | false | `safety_template` |
| `OUT_OF_SCOPE` | `out_of_scope` | 5.3 (approved) | false | `safety_template` |
| `INVALID_INPUT` | `invalid_input` | 5.5 (existing; selection rule above) | false | `input_check` |
| `PROCEED` | `mock_answer` | 5.5 (existing mock) | **true** | `mock_placeholder` |

The router's priority order and rules are unchanged (D-17, v0.1.1). The topic matcher is not called, so `abstained` is always `false` and `abstain_reason` always `null` in this integration.

## 7. Approved: API Contract v0.2

**Problem addressed.** Contract v0.1 requires `is_mock: true` on every reply and a visible "Mock response" label whenever `is_mock` is true. Once the router is connected, real safety guidance would carry a "Mock response" label, which could lead people to discount it.

**Approved changes** (everything else in `docs/API_CONTRACT.md` stays the same):

| Field | v0.1 | v0.2 |
|---|---|---|
| `api_version` | `"0.1"` | `"0.2"` |
| `is_mock` | Literal `true` | Boolean. **`true` if and only if `kind` is `mock_answer`.** The response model enforces this pairing. |
| `content_source` | — | **New, required.** `"mock_placeholder"` (kind `mock_answer`), `"safety_template"` (`emergency`, `crisis`, `decline_diagnosis`, `decline_dosage`, `out_of_scope`, `safe_fallback`), or `"input_check"` (`invalid_input`). Reserved for later: `"reviewed_content"`, only after a reviewed answer source and its own decision. |
| `versions.router` | `null` | See the rule below. |
| `versions.content` | `"mock"` | Version of the fixed template set, for example `"templates-0.1"`, so a reply can be traced to the approved wording. |
| `versions.matcher` | `null` | Stays `null` (matcher not connected). |
| `GET /api/health` `mode` | `"mock"` | `"router_only"` |

**`versions.router` rule (approved: `null` whenever the router was not actually executed).** In a `/api/chat` response, `versions.router` is the router version (`"0.1.1"`) only when `safety.route()` ran and returned a decision produced by its rules. It is `null` when:

- the router was not called (for example, a pipeline failure before routing);
- the call raised an exception; or
- the router returned its own internal-error fallback (reason code `router:error`), because then no routing rules were applied.

In each of those cases the reply is the safe fallback (5.4), without technical details. The same applies to any other internal error after routing: the fail-closed reply is not based on a routing decision, so `versions.router` is `null`.

**Health check `versions` (approved).** `GET /api/health` reports the **configured, connected** components, not the execution of the router for any request: `mode: "router_only"`, `versions.router: "0.1.1"`, `versions.matcher: null`, `versions.content: "templates-0.1"`.

**Approved frontend rules (v0.2):**

- Show "Mock response" only when `is_mock` is true.
- For `content_source: "safety_template"`, show a label such as "Automated safety message (prototype)". The label must not suggest clinical review or validation.
- Show `emergency` and `crisis` replies first and prominently, with an icon and a text heading (never colour alone), announced to screen readers as an alert.
- Treat any unknown `kind` or `content_source` as `safe_fallback` (unchanged rule).
- The disclaimer and safety notice stay visible.

**Unchanged:** request schema, validation order, the 128 KiB body limit, error envelope and codes, `request_id`, `Cache-Control: no-store`, disabled docs routes, privacy rules, no dataset answers, no diagnostics by default, local-only development.

### Example payloads (v0.2)

Mock placeholder (`PROCEED`):

```json
{
  "api_version": "0.2",
  "request_id": "0b6c1f4e-6a4f-4d5e-9d8e-2f3a1c7b9e10",
  "kind": "mock_answer",
  "content_source": "mock_placeholder",
  "message": {
    "title": "Mock response: answers are not available yet",
    "paragraphs": [
      "This is a placeholder. QueryMate's answer system is not connected, so your question has not been checked or answered.",
      "For health concerns, please consult a qualified healthcare professional. If you think you may be experiencing an emergency, contact local emergency services immediately."
    ]
  },
  "is_mock": true,
  "abstained": false,
  "abstain_reason": null,
  "disclaimer": "QueryMate provides general health information and is not a substitute for professional medical advice, diagnosis, or treatment. If you think you may be experiencing an emergency, contact local emergency services immediately.",
  "versions": { "router": "0.1.1", "matcher": null, "content": "templates-0.1" }
}
```

Emergency (approved):

```json
{
  "api_version": "0.2",
  "request_id": "5d2e8a91-3c47-4b0f-8e6d-7a1b2c3d4e5f",
  "kind": "emergency",
  "content_source": "safety_template",
  "message": {
    "title": "Possible emergency",
    "paragraphs": [
      "If you or someone else may be in immediate danger, contact local emergency services immediately.",
      "QueryMate is an educational prototype and cannot provide crisis intervention or assess immediate safety. Do not wait for a response from QueryMate if urgent help may be needed."
    ]
  },
  "is_mock": false,
  "abstained": false,
  "abstain_reason": null,
  "disclaimer": "QueryMate provides general health information and is not a substitute for professional medical advice, diagnosis, or treatment. If you think you may be experiencing an emergency, contact local emergency services immediately.",
  "versions": { "router": "0.1.1", "matcher": null, "content": "templates-0.1" }
}
```

Crisis (approved):

```json
{
  "api_version": "0.2",
  "request_id": "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d",
  "kind": "crisis",
  "content_source": "safety_template",
  "message": {
    "title": "Please get help now",
    "paragraphs": [
      "If you or someone else may be in immediate danger, contact local emergency services immediately.",
      "QueryMate is an educational prototype and cannot provide crisis intervention or assess immediate safety. Do not wait for a response from QueryMate if urgent help may be needed.",
      "If you are thinking about harming yourself, please reach out to someone you trust who can support you now. If you or someone else may have taken too much of a medicine or other substance, seek emergency help immediately. If possible, stay with someone you trust while getting help."
    ]
  },
  "is_mock": false,
  "abstained": false,
  "abstain_reason": null,
  "disclaimer": "QueryMate provides general health information and is not a substitute for professional medical advice, diagnosis, or treatment. If you think you may be experiencing an emergency, contact local emergency services immediately.",
  "versions": { "router": "0.1.1", "matcher": null, "content": "templates-0.1" }
}
```

Dosage request (approved):

```json
{
  "api_version": "0.2",
  "request_id": "1f2e3d4c-5b6a-4978-8a9b-0c1d2e3f4a5b",
  "kind": "decline_dosage",
  "content_source": "safety_template",
  "message": {
    "title": "QueryMate can't advise on medicines or doses",
    "paragraphs": [
      "QueryMate is an educational prototype and cannot recommend medicines, suggest doses, or advise on starting, stopping, changing, or combining medicines.",
      "For questions about medicines, please ask a pharmacist, your prescriber, or another qualified healthcare professional, or check the official information leaflet that comes with the medicine.",
      "If you think you may be experiencing an emergency, contact local emergency services immediately."
    ]
  },
  "is_mock": false,
  "abstained": false,
  "abstain_reason": null,
  "disclaimer": "QueryMate provides general health information and is not a substitute for professional medical advice, diagnosis, or treatment. If you think you may be experiencing an emergency, contact local emergency services immediately.",
  "versions": { "router": "0.1.1", "matcher": null, "content": "templates-0.1" }
}
```

Input check, empty question (existing wording):

```json
{
  "api_version": "0.2",
  "request_id": "7c6b5a49-3827-4161-9f0e-d1c2b3a49586",
  "kind": "invalid_input",
  "content_source": "input_check",
  "message": {
    "title": "Please enter a question.",
    "paragraphs": ["Type a general health question, then send it."]
  },
  "is_mock": false,
  "abstained": false,
  "abstain_reason": null,
  "disclaimer": "QueryMate provides general health information and is not a substitute for professional medical advice, diagnosis, or treatment. If you think you may be experiencing an emergency, contact local emergency services immediately.",
  "versions": { "router": "0.1.1", "matcher": null, "content": "templates-0.1" }
}
```

Input check, over-length question with no crisis or emergency signal (existing wording):

```json
{
  "api_version": "0.2",
  "request_id": "3e4d5c6b-7a89-4b0c-9d1e-2f3a4b5c6d7e",
  "kind": "invalid_input",
  "content_source": "input_check",
  "message": {
    "title": "Your question is too long.",
    "paragraphs": [
      "Please shorten it to 1,000 characters or fewer.",
      "If you think you may be experiencing an emergency, contact local emergency services immediately."
    ]
  },
  "is_mock": false,
  "abstained": false,
  "abstain_reason": null,
  "disclaimer": "QueryMate provides general health information and is not a substitute for professional medical advice, diagnosis, or treatment. If you think you may be experiencing an emergency, contact local emergency services immediately.",
  "versions": { "router": "0.1.1", "matcher": null, "content": "templates-0.1" }
}
```

Safe fallback after a router internal error (`versions.router` is `null`):

```json
{
  "api_version": "0.2",
  "request_id": "8f7e6d5c-4b3a-4291-8e7f-6a5b4c3d2e1f",
  "kind": "safe_fallback",
  "content_source": "safety_template",
  "message": {
    "title": "QueryMate can't answer this safely",
    "paragraphs": [
      "I couldn't find enough reliable information to answer this safely. Please rephrase your question or consult a qualified healthcare professional.",
      "If you think you may be experiencing an emergency, contact local emergency services immediately."
    ]
  },
  "is_mock": false,
  "abstained": false,
  "abstain_reason": null,
  "disclaimer": "QueryMate provides general health information and is not a substitute for professional medical advice, diagnosis, or treatment. If you think you may be experiencing an emergency, contact local emergency services immediately.",
  "versions": { "router": null, "matcher": null, "content": "templates-0.1" }
}
```

## 8. Owner actions (all resolved 2026-10-20)

1. Crisis-support paragraph: **provided and approved** (section 3).
2. `versions.router` rule: **confirmed** (section 7). `null` when the router was not called, raised an exception, or returned `router:error`; `"0.1.1"` only when the router ran and produced the routing decision.
3. Health check `versions`: **approved** to report connected components (section 7).

## 9. Progress and next steps

Done (documentation only, 2026-10-20):

1. Approved wording checked against section 3's requirements and against the v0.2 contract.
2. `docs/API_CONTRACT.md` updated to v0.2 (including the full approved template text).
3. **D-20** recorded in `docs/DECISIONS.md`. Existing entries were not changed or renumbered.

Done (each approved separately by the owner):

4. Phase A: `src/querymate/pipeline.py` and fixed templates, with tests (`tests/test_pipeline.py`: router before any matching, matcher never called, fail-closed errors, no echo, no dataset answers).
5. Phase B: FastAPI delegates to the pipeline and serves contract v0.2 (`src/querymate/api/`, `tests/test_api.py`).
6. Phase C: React calls the API through the Vite proxy and validates every reply against v0.2 before showing it (`frontend/src/api/`, frontend tests).

Each phase's tests must pass before the next phase starts. The owner reviews at the end.

## 10. Not affected by this review

Safety router rules and the frozen v0.1.0 artifact; historical reports; evaluation sets and labels; curated topics and examples (all remain `pending_owner_review`); the dataset CSV and ZIP; the Streamlit reference UI; the current mock-only API (contract v0.1, `mock` mode) and the React frontend.
