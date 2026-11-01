// Types for docs/API_CONTRACT.md v0.3 (curated_single_topic mode, D-21).
// Mirrors src/querymate/api/schemas.py. Runtime checks live in ./validate.ts.

export const KINDS = [
  "curated_answer",
  "mock_answer",
  "safe_fallback",
  "emergency",
  "crisis",
  "decline_diagnosis",
  "decline_dosage",
  "out_of_scope",
  "invalid_input",
] as const;
export type Kind = (typeof KINDS)[number];

// "reviewed_content" is reserved by the contract and deliberately not accepted.
export const CONTENT_SOURCES = ["curated_owner_reviewed", "mock_placeholder", "safety_template", "input_check"] as const;
export type ContentSource = (typeof CONTENT_SOURCES)[number];

// API_CONTRACT v0.3 "kind values": content_source is determined by kind.
export const CONTENT_SOURCE_BY_KIND: Record<Kind, ContentSource> = {
  curated_answer: "curated_owner_reviewed",
  mock_answer: "mock_placeholder",
  invalid_input: "input_check",
  emergency: "safety_template",
  crisis: "safety_template",
  decline_diagnosis: "safety_template",
  decline_dosage: "safety_template",
  out_of_scope: "safety_template",
  safe_fallback: "safety_template",
};

export type AbstainReason =
  | "no_overlap"
  | "below_min_score"
  | "below_min_margin"
  | "matcher_unavailable";

export interface ReplyMessage {
  title: string;
  paragraphs: string[];
}

export interface Source {
  title: string;
  organization: string;
  url: string; // https only
}

// Owner review of educational content; never clinical review.
export type ReviewStatus = "owner_reviewed";

export interface Versions {
  router: string | null; // "0.1.1" only when the reply is based on a router decision
  matcher: null; // the matcher is not connected
  content: "templates-0.1";
  knowledge: string | null; // set only on curated answers
}

export interface ChatResponse {
  api_version: "0.3";
  request_id: string;
  kind: Kind;
  content_source: ContentSource;
  message: ReplyMessage;
  sources: Source[]; // non-empty if and only if kind is "curated_answer"
  review_status: ReviewStatus | null; // set if and only if kind is "curated_answer"
  is_mock: boolean; // true if and only if kind is "mock_answer"
  abstained: boolean; // always false: the matcher is not connected
  abstain_reason: AbstainReason | null; // always null: the matcher is not connected
  disclaimer: string;
  versions: Versions;
}

/**
 * What the UI receives for one question. "unrecognised" means the server sent a
 * well-formed reply whose kind or content_source this client does not know; the
 * contract says to treat it as safe_fallback, so its text is never shown.
 */
export type ChatOutcome = { type: "reply"; response: ChatResponse } | { type: "unrecognised" };

/** Why a request produced no displayable reply. Never carries server or user text. */
export type ChatErrorKind = "network" | "timeout" | "http" | "invalid_response" | "aborted";

export class ChatError extends Error {
  readonly kind: ChatErrorKind;
  constructor(kind: ChatErrorKind) {
    super(`chat request failed: ${kind}`);
    this.name = "ChatError";
    this.kind = kind;
  }
}

/** Anything that can answer a question: the FastAPI client, or a stub in tests. */
export interface ChatClient {
  chat(question: string, signal?: AbortSignal): Promise<ChatOutcome>;
}
