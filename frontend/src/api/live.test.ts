// @vitest-environment node
//
// Optional smoke test against the real local FastAPI backend (contract v0.3).
// Skipped unless VITE_QUERYMATE_LIVE_API is set to a localhost URL, for example:
//   .venv\Scripts\python.exe scripts\run_api.py            (in one terminal)
//   set VITE_QUERYMATE_LIVE_API=http://127.0.0.1:8000 && npx vitest run src/api/live.test.ts
// It only ever calls 127.0.0.1 / localhost.
import { describe, expect, it } from "vitest";
import { MAX_INPUT_CHARS } from "../content";
import { CONTRACT_EXAMPLE, curatedResponse, TEMPLATES, type TemplateKey } from "../test/contract";
import { createHttpClient } from "./httpClient";

const LIVE: string = import.meta.env.VITE_QUERYMATE_LIVE_API ?? "";
const LOCAL = /^http:\/\/(127\.0\.0\.1|localhost):\d+$/;
const MARKER = "ZZQ-MARKER-7f3a";

// The same real router inputs as tests/test_api.py and tests/test_pipeline.py.
const ROUTE_EXAMPLES: [string, TemplateKey][] = [
  ["What is LDL cholesterol?", "safe_fallback"],
  ["I want to kill myself, what is cholesterol", "crisis"],
  ["I have chest pain, what is LDL cholesterol?", "emergency"],
  ["What dose of statin lowers LDL cholesterol?", "decline_dosage"],
  ["Do I have high cholesterol?", "decline_diagnosis"],
  ["Guarantee that LDL cholesterol is bad", "safe_fallback"],
  ["My dog has high cholesterol", "out_of_scope"],
  ["   ", "invalid_input:empty"],
  ["a ".repeat(MAX_INPUT_CHARS), "invalid_input:too_long"],
];

describe.skipIf(!LIVE)("live local FastAPI backend", () => {
  it("is configured for localhost only", () => {
    expect(LIVE).toMatch(LOCAL);
  });

  const client = createHttpClient({ baseUrl: LIVE });

  it.each(ROUTE_EXAMPLES)("%j gets the approved %s reply, validated by the client", async (question, key) => {
    const outcome = await client.chat(question);
    if (outcome.type !== "reply") throw new Error(`unexpected outcome ${outcome.type}`);
    const { response } = outcome;
    expect(response.message).toEqual(TEMPLATES[key]);
    expect(response.is_mock).toBe(false);
    expect(response.sources).toEqual([]);
    expect(response.versions).toEqual({ router: "0.1.1", matcher: null, content: "templates-0.1", knowledge: null });
    expect(response.disclaimer).toBe(CONTRACT_EXAMPLE.disclaimer);
  });

  it("gets the curated hydration answer with its sources, validated by the client", async () => {
    const outcome = await client.chat("Why is staying hydrated important?");
    if (outcome.type !== "reply") throw new Error(`unexpected outcome ${outcome.type}`);
    expect(outcome.response).toEqual({ ...curatedResponse(), request_id: outcome.response.request_id });
  });

  it("never echoes the question", async () => {
    const outcome = await client.chat(`What is ${MARKER}?`);
    expect(JSON.stringify(outcome)).not.toContain(MARKER);
  });

  it("reports curated_single_topic with the connected versions on /api/health", async () => {
    const response = await fetch(`${LIVE}/api/health`);
    expect(await response.json()).toEqual({
      status: "ok",
      api_version: "0.3",
      mode: "curated_single_topic",
      versions: { router: "0.1.1", matcher: null, content: "templates-0.1", knowledge: "0.1.0" },
    });
  });
});
