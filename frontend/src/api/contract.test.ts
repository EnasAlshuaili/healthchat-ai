// The frontend's view of API Contract v0.3, checked against docs/API_CONTRACT.md.
import { describe, expect, it } from "vitest";
import { CURATED_LABEL, SAFE_FALLBACK_REPLY, DISCLAIMER, MOCK_LABEL, SAFETY_LABEL } from "../content";
import { CONTRACT_EXAMPLE, CONTRACT_TEXT, TEMPLATES, TEMPLATE_KEYS, contractResponse } from "../test/contract";
import { CONTENT_SOURCES, CONTENT_SOURCE_BY_KIND, KINDS } from "./types";
import { validateChatResponse } from "./validate";

describe("contract v0.3 as seen by the frontend", () => {
  it("parses all nine approved templates from the contract", () => {
    expect(TEMPLATE_KEYS.sort()).toEqual(
      [
        "crisis",
        "decline_diagnosis",
        "decline_dosage",
        "emergency",
        "invalid_input:empty",
        "invalid_input:too_long",
        "mock_answer",
        "out_of_scope",
        "safe_fallback",
      ].sort(),
    );
    expect(TEMPLATES.emergency.title).toBe("Possible emergency");
    expect(TEMPLATES.crisis.paragraphs).toHaveLength(3);
  });

  it("lists every kind and content_source from the contract's kind table, and no others", () => {
    const table = CONTRACT_TEXT.slice(CONTRACT_TEXT.indexOf("### `kind` values"), CONTRACT_TEXT.indexOf("### Reply templates"));
    const rows = [...table.matchAll(/^\| `(\w+)` \| `(\w+)` \| `(true|false)` \|/gm)].map(([, kind, source, mock]) => ({
      kind,
      source,
      mock: mock === "true",
    }));
    expect(rows.map((r) => r.kind).sort()).toEqual([...KINDS].sort());
    for (const { kind, source, mock } of rows) {
      expect(CONTENT_SOURCE_BY_KIND[kind as keyof typeof CONTENT_SOURCE_BY_KIND]).toBe(source);
      expect(mock).toBe(kind === "mock_answer");
    }
    expect([...CONTENT_SOURCES].sort()).toEqual([
      "curated_owner_reviewed",
      "input_check",
      "mock_placeholder",
      "safety_template",
    ]);
    expect(CONTENT_SOURCES as readonly string[]).not.toContain("reviewed_content");
  });

  it("accepts the contract's documented example exactly", () => {
    const result = validateChatResponse(CONTRACT_EXAMPLE);
    expect(result).toEqual({ status: "valid", response: CONTRACT_EXAMPLE });
  });

  it("documents a curated answer with its sources as the 200 example", () => {
    expect(CONTRACT_EXAMPLE.kind).toBe("curated_answer");
    expect(CONTRACT_EXAMPLE.review_status).toBe("owner_reviewed");
    expect(CONTRACT_EXAMPLE.sources).toHaveLength(3);
    expect(CONTRACT_EXAMPLE.message.paragraphs.join(" ")).toContain(
      "has not been clinically reviewed or clinically validated",
    );
  });

  it("accepts a contract response for every template", () => {
    for (const key of TEMPLATE_KEYS) {
      expect(validateChatResponse(contractResponse(key)).status, key).toBe("valid");
    }
  });

  it("keeps the local disclaimer identical to the contract's", () => {
    expect(CONTRACT_EXAMPLE.disclaimer).toBe(DISCLAIMER);
  });

  it("keeps the local safe_fallback copy identical to the approved template", () => {
    expect({ title: SAFE_FALLBACK_REPLY.title, paragraphs: [...SAFE_FALLBACK_REPLY.paragraphs] }).toEqual(
      TEMPLATES.safe_fallback,
    );
  });

  it("uses the labels the contract names, with no claim of review", () => {
    expect(MOCK_LABEL).toBe("Mock response");
    expect(SAFETY_LABEL).toBe("Automated safety message (prototype)");
    expect(SAFETY_LABEL).not.toMatch(/review|validat|verif|clinic|approved/i);
    expect(CURATED_LABEL).toBe("Educational content: owner reviewed, not clinically reviewed");
    expect(CONTRACT_TEXT).toContain(CURATED_LABEL);
  });
});
