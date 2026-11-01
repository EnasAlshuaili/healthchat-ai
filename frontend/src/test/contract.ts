// Test fixtures built from docs/API_CONTRACT.md itself (v0.3 "Reply templates" and the
// documented 200 example), so the frontend is tested against the approved wording,
// not a copy that could drift. Read-only; never bundled into the app.
import contract from "../../../docs/API_CONTRACT.md?raw";
import { CONTENT_SOURCE_BY_KIND, KINDS, type ChatResponse, type Kind, type ReplyMessage } from "../api/types";

export const CONTRACT_TEXT: string = contract;

function section(start: string, end: string): string {
  const from = contract.indexOf(start);
  const to = contract.indexOf(end, from);
  if (from < 0 || to < 0) throw new Error(`API_CONTRACT.md section not found: ${start}`);
  return contract.slice(from, to);
}

/** Template key: a kind, or "invalid_input:empty" / "invalid_input:too_long". */
export type TemplateKey =
  | Exclude<Kind, "invalid_input" | "curated_answer">
  | "invalid_input:empty"
  | "invalid_input:too_long";

const VARIANTS: Record<string, TemplateKey> = {
  "empty question": "invalid_input:empty",
  "over-length question": "invalid_input:too_long",
};

function parseTemplates(): Record<TemplateKey, ReplyMessage> {
  const templates: Partial<Record<TemplateKey, ReplyMessage>> = {};
  let current: ReplyMessage | null = null;
  for (const line of section("### Reply templates", "### Fail-safe rules").split(/\r?\n/)) {
    const header = /^\*\*`(\w+)`(?:, ([^*]+))?\*\*: title "(.+)"$/.exec(line);
    if (header) {
      const [, kind, variant, title] = header;
      const key = (variant ? VARIANTS[variant] : kind) as TemplateKey;
      if (!key) throw new Error(`Unknown template variant: ${variant}`);
      current = { title, paragraphs: [] };
      templates[key] = current;
      continue;
    }
    const item = /^\d+\. (.+)$/.exec(line);
    if (item && current) current.paragraphs.push(item[1]);
    else if (line.startsWith("Caveats")) current = null;
  }
  return templates as Record<TemplateKey, ReplyMessage>;
}

export const TEMPLATES = parseTemplates();
export const TEMPLATE_KEYS = Object.keys(TEMPLATES) as TemplateKey[];

/** The documented `200 OK` example body, verbatim. */
export const CONTRACT_EXAMPLE: ChatResponse = JSON.parse(
  /```json\r?\n([\s\S]*?)```/.exec(section("### Response: `200 OK`", "| Field |"))![1],
);

export function kindOf(key: TemplateKey): Kind {
  return key.startsWith("invalid_input") ? "invalid_input" : (key as Kind);
}

let counter = 0;

/** The documented curated answer, as the server would send it (a fresh copy each time). */
export function curatedResponse(): ChatResponse {
  return structuredClone(CONTRACT_EXAMPLE);
}

/** A contract-valid v0.3 body for a template, as the server would send it. */
export function contractResponse(key: TemplateKey, router: string | null = "0.1.1"): ChatResponse {
  const kind = kindOf(key);
  const message = TEMPLATES[key];
  counter += 1;
  return {
    ...CONTRACT_EXAMPLE,
    request_id: `00000000-0000-4000-8000-${String(counter).padStart(12, "0")}`,
    kind,
    content_source: CONTENT_SOURCE_BY_KIND[kind],
    message: { title: message.title, paragraphs: [...message.paragraphs] },
    sources: [],
    review_status: null,
    is_mock: kind === "mock_answer",
    versions: { router, matcher: null, content: "templates-0.1", knowledge: null },
  };
}

// Sanity: every kind has a template, except curated answers (the documented example).
for (const kind of KINDS) {
  if (kind === "curated_answer") continue;
  if (!TEMPLATE_KEYS.some((key) => kindOf(key) === kind)) throw new Error(`No template for ${kind}`);
}
