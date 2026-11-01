import { describe, expect, it } from "vitest";
import { contractResponse, curatedResponse, TEMPLATE_KEYS } from "../test/contract";
import { validateChatResponse } from "./validate";

type Body = Record<string, unknown>;

/** A valid body with one change applied (a deep copy, so fixtures are never shared). */
function variant(change: (body: Body) => void, key: Parameters<typeof contractResponse>[0] = "emergency"): Body {
  const body = structuredClone(contractResponse(key)) as unknown as Body;
  change(body);
  return body;
}

const status = (body: unknown) => validateChatResponse(body).status;

describe("validateChatResponse: valid bodies", () => {
  it("accepts every approved template, with router 0.1.1 or null", () => {
    for (const key of TEMPLATE_KEYS) {
      expect(status(contractResponse(key)), key).toBe("valid");
      expect(status(contractResponse(key, null)), key).toBe("valid");
    }
  });

  it("returns the body's own values, copied and not filled in", () => {
    const body = contractResponse("crisis");
    const result = validateChatResponse(body);
    if (result.status !== "valid") throw new Error("expected valid");
    expect(result.response).toEqual(body);
    body.message.paragraphs[0] = "changed after validation";
    expect(result.response.message.paragraphs[0]).not.toBe("changed after validation");
  });

  it("accepts the developer-only diagnostics field but never passes it on", () => {
    const body = variant((b) => (b.diagnostics = { route: "proceed", reason_codes: ["x"] }), "mock_answer");
    const result = validateChatResponse(body);
    expect(result.status).toBe("valid");
    expect(result.status === "valid" && "diagnostics" in result.response).toBe(false);
  });
});

const curated = (change: (body: Body) => void): Body => {
  const body = curatedResponse() as unknown as Body;
  change(body);
  return body;
};
const SOURCE = { title: "T", organization: "O", url: "https://example.org/" };

describe("validateChatResponse: curated answers", () => {
  it("accepts a curated answer and returns its sources, copied", () => {
    const body = curatedResponse();
    const result = validateChatResponse(body);
    if (result.status !== "valid") throw new Error("expected valid");
    expect(result.response).toEqual(body);
    body.sources[0].title = "changed after validation";
    expect(result.response.sources[0].title).not.toBe("changed after validation");
  });

  it.each<[string, (b: Body) => void]>([
    ["no sources", (b) => (b.sources = [])],
    ["sources that are not a list", (b) => (b.sources = "https://example.org/")],
    ["a null source", (b) => (b.sources = [null])],
    ["a source without a url", (b) => (b.sources = [{ title: "T", organization: "O" }])],
    ["an extra source field", (b) => (b.sources = [{ ...SOURCE, html: "<b>" }])],
    ["an empty source title", (b) => (b.sources = [{ ...SOURCE, title: " " }])],
    ["an empty organization", (b) => (b.sources = [{ ...SOURCE, organization: "" }])],
    ["an http url", (b) => (b.sources = [{ ...SOURCE, url: "http://example.org/" }])],
    ["a javascript url", (b) => (b.sources = [{ ...SOURCE, url: "javascript:alert(1)" }])],
    ["a data url", (b) => (b.sources = [{ ...SOURCE, url: "data:text/html,x" }])],
    ["a relative url", (b) => (b.sources = [{ ...SOURCE, url: "/page" }])],
    ["a url with spaces", (b) => (b.sources = [{ ...SOURCE, url: "https://example.org/a b" }])],
    ["a missing review_status", (b) => (b.review_status = null)],
    ["a pending review_status", (b) => (b.review_status = "pending_owner_review")],
    ["a clinical review_status", (b) => (b.review_status = "clinically_reviewed")],
    ["a missing knowledge version", (b) => ((b.versions as Body).knowledge = null)],
    ["a null router version", (b) => ((b.versions as Body).router = null)],
    ["is_mock true", (b) => (b.is_mock = true)],
    ["a safety content_source", (b) => (b.content_source = "safety_template")],
  ])("rejects a curated answer with %s", (_name, change) => {
    expect(status(curated(change))).toBe("invalid");
  });

  it("rejects curated fields on every other reply, so safety replies never carry sources", () => {
    for (const key of TEMPLATE_KEYS) {
      expect(status(variant((b) => (b.sources = [SOURCE]), key)), key).toBe("invalid");
      expect(status(variant((b) => (b.review_status = "owner_reviewed"), key)), key).toBe("invalid");
      expect(status(variant((b) => ((b.versions as Body).knowledge = "0.1.0"), key)), key).toBe("invalid");
    }
  });
});

describe("validateChatResponse: unknown kind or content_source (treated as safe_fallback)", () => {
  it.each([
    ["an unknown kind", (b: Body) => (b.kind = "medical_advice")],
    ["the reserved reviewed_content source", (b: Body) => (b.content_source = "reviewed_content")],
    ["an unknown content_source", (b: Body) => (b.content_source = "dataset")],
  ])("reports %s as unrecognised", (_name, change) => {
    expect(status(variant(change))).toBe("unrecognised");
  });
});

describe("validateChatResponse: rejected bodies", () => {
  it.each([null, undefined, "text", 42, true, [], [contractResponse("emergency")]])("rejects non-object %#", (body) => {
    expect(status(body)).toBe("invalid");
  });

  it("rejects a body missing any required field", () => {
    for (const field of Object.keys(contractResponse("emergency"))) {
      expect(status(variant((b) => delete b[field])), field).toBe("invalid");
    }
  });

  it("rejects unknown fields, including __proto__", () => {
    expect(status(variant((b) => (b.answer = "dataset text")))).toBe("invalid");
    expect(status(JSON.parse(`{"__proto__": {"x": 1}, ${JSON.stringify(contractResponse("emergency")).slice(1)}`))).toBe(
      "invalid",
    );
  });

  it.each<[string, (b: Body) => void]>([
    ["api_version 0.1", (b) => (b.api_version = "0.1")],
    ["api_version 0.2", (b) => (b.api_version = "0.2")],
    ["api_version as a number", (b) => (b.api_version = 0.3)],
    ["an empty request_id", (b) => (b.request_id = "")],
    ["a non-string request_id", (b) => (b.request_id = 1)],
    ["a non-string kind", (b) => (b.kind = 1)],
    ["a non-string content_source", (b) => (b.content_source = null)],
    ["is_mock as a string", (b) => (b.is_mock = "false")],
    ["is_mock as a number", (b) => (b.is_mock = 0)],
    ["abstained as a string", (b) => (b.abstained = "false")],
    ["abstained true", (b) => (b.abstained = true)],
    ["an abstain_reason", (b) => (b.abstain_reason = "no_overlap")],
    ["an empty disclaimer", (b) => (b.disclaimer = " ")],
    ["a missing message", (b) => (b.message = null)],
    ["an empty title", (b) => (b.message = { title: "", paragraphs: ["x"] })],
    ["no paragraphs", (b) => (b.message = { title: "t", paragraphs: [] })],
    ["six paragraphs", (b) => (b.message = { title: "t", paragraphs: ["1", "2", "3", "4", "5", "6"] })],
    ["a non-string paragraph", (b) => (b.message = { title: "t", paragraphs: ["x", 5] })],
    ["an empty paragraph", (b) => (b.message = { title: "t", paragraphs: ["x", ""] })],
    ["paragraphs as a string", (b) => (b.message = { title: "t", paragraphs: "x" })],
    ["an extra message field", (b) => (b.message = { title: "t", paragraphs: ["x"], html: "<b>" })],
    ["missing versions", (b) => (b.versions = null)],
    ["a matcher version", (b) => (b.versions = { router: "0.1.1", matcher: "0.1", content: "templates-0.1", knowledge: null })],
    ["v0.1 content version", (b) => (b.versions = { router: null, matcher: null, content: "mock", knowledge: null })],
    ["a non-string router version", (b) => (b.versions = { router: 1, matcher: null, content: "templates-0.1", knowledge: null })],
    ["a missing router version", (b) => (b.versions = { matcher: null, content: "templates-0.1", knowledge: null })],
    ["a missing knowledge version", (b) => (b.versions = { router: null, matcher: null, content: "templates-0.1" })],
    ["a non-string knowledge version", (b) => (b.versions = { router: null, matcher: null, content: "templates-0.1", knowledge: 1 })],
    [
      "an extra versions field",
      (b) => (b.versions = { router: null, matcher: null, content: "templates-0.1", knowledge: null, x: 1 }),
    ],
  ])("rejects %s", (_name, change) => {
    expect(status(variant(change))).toBe("invalid");
  });

  it("rejects is_mock that does not match kind", () => {
    expect(status(variant((b) => (b.is_mock = true), "emergency"))).toBe("invalid");
    expect(status(variant((b) => (b.is_mock = true), "invalid_input:empty"))).toBe("invalid");
    expect(status(variant((b) => (b.is_mock = false), "mock_answer"))).toBe("invalid");
  });

  it("rejects a content_source that does not match kind", () => {
    expect(status(variant((b) => (b.content_source = "input_check"), "crisis"))).toBe("invalid");
    expect(status(variant((b) => (b.content_source = "safety_template"), "mock_answer"))).toBe("invalid");
    expect(status(variant((b) => (b.content_source = "mock_placeholder"), "invalid_input:too_long"))).toBe("invalid");
  });
});
