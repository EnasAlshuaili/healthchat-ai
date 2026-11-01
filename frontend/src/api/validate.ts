// Runtime check of a /api/chat body against docs/API_CONTRACT.md v0.3 (curated_single_topic).
//
// Nothing is repaired or filled in: a body either matches the contract exactly and
// is copied field by field, or it is rejected. The only exception is the contract's
// own rule that an unknown kind or content_source is treated as safe_fallback,
// which is reported as "unrecognised" so the UI never shows that body's text.

import {
  CONTENT_SOURCES,
  CONTENT_SOURCE_BY_KIND,
  KINDS,
  type ChatResponse,
  type ContentSource,
  type Kind,
  type Source,
} from "./types";

export type Validation =
  | { status: "valid"; response: ChatResponse }
  | { status: "unrecognised" }
  | { status: "invalid" };

const FIELDS = [
  "api_version",
  "request_id",
  "kind",
  "content_source",
  "message",
  "sources",
  "review_status",
  "is_mock",
  "abstained",
  "abstain_reason",
  "disclaimer",
  "versions",
] as const;
// Developer-only and off by default (contract "Diagnostics"); accepted but never read or shown.
const IGNORED_FIELDS = new Set(["diagnostics"]);
const MAX_PARAGRAPHS = 5;

type Json = Record<string, unknown>;

function isObject(value: unknown): value is Json {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasExactKeys(value: Json, required: readonly string[], ignored = new Set<string>()): boolean {
  const keys = Object.keys(value);
  return (
    required.every((key) => Object.hasOwn(value, key)) &&
    keys.every((key) => required.includes(key) || ignored.has(key))
  );
}

function isText(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isHttpsUrl(value: unknown): value is string {
  if (typeof value !== "string" || !value.startsWith("https://") || /\s/.test(value)) return false;
  try {
    return new URL(value).protocol === "https:";
  } catch {
    return false;
  }
}

function isSource(value: unknown): value is Source {
  return (
    isObject(value) &&
    hasExactKeys(value, ["title", "organization", "url"]) &&
    isText(value.title) &&
    isText(value.organization) &&
    isHttpsUrl(value.url)
  );
}

const INVALID: Validation = { status: "invalid" };

export function validateChatResponse(body: unknown): Validation {
  if (!isObject(body) || !hasExactKeys(body, FIELDS, IGNORED_FIELDS)) return INVALID;
  const {
    api_version,
    request_id,
    kind,
    content_source,
    message,
    sources,
    review_status,
    is_mock,
    abstained,
    abstain_reason,
    disclaimer,
    versions,
  } = body;

  if (api_version !== "0.3" || !isText(request_id) || !isText(disclaimer)) return INVALID;
  if (typeof kind !== "string" || typeof content_source !== "string") return INVALID;
  if (typeof is_mock !== "boolean" || typeof abstained !== "boolean") return INVALID;

  if (!isObject(message) || !hasExactKeys(message, ["title", "paragraphs"])) return INVALID;
  const { title, paragraphs } = message;
  if (!isText(title) || !Array.isArray(paragraphs)) return INVALID;
  if (paragraphs.length < 1 || paragraphs.length > MAX_PARAGRAPHS || !paragraphs.every(isText)) return INVALID;

  if (!Array.isArray(sources) || !sources.every(isSource)) return INVALID;
  if (review_status !== null && review_status !== "owner_reviewed") return INVALID;

  if (!isObject(versions) || !hasExactKeys(versions, ["router", "matcher", "content", "knowledge"])) return INVALID;
  if (!(versions.router === null || isText(versions.router))) return INVALID;
  if (!(versions.knowledge === null || isText(versions.knowledge))) return INVALID;
  if (versions.matcher !== null || versions.content !== "templates-0.1") return INVALID;

  // The matcher is not connected, so nothing can abstain.
  if (abstained !== false || abstain_reason !== null) return INVALID;

  if (!(KINDS as readonly string[]).includes(kind) || !(CONTENT_SOURCES as readonly string[]).includes(content_source)) {
    return { status: "unrecognised" };
  }
  const knownKind = kind as Kind;
  if (content_source !== CONTENT_SOURCE_BY_KIND[knownKind]) return INVALID;
  if (is_mock !== (knownKind === "mock_answer")) return INVALID;

  // Curated fields belong to curated answers only: a safety reply can never carry sources.
  const curated = knownKind === "curated_answer";
  if (curated !== sources.length > 0) return INVALID;
  if (curated !== (review_status !== null)) return INVALID;
  if (curated !== (versions.knowledge !== null)) return INVALID;
  if (curated && versions.router === null) return INVALID;

  return {
    status: "valid",
    response: {
      api_version: "0.3",
      request_id,
      kind: knownKind,
      content_source: content_source as ContentSource,
      message: { title, paragraphs: [...(paragraphs as string[])] },
      sources: sources.map(({ title, organization, url }) => ({ title, organization, url })),
      review_status,
      is_mock,
      abstained: false,
      abstain_reason: null,
      disclaimer,
      versions: { router: versions.router, matcher: null, content: "templates-0.1", knowledge: versions.knowledge },
    },
  };
}
