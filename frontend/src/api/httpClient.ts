// FastAPI client for POST /api/chat (docs/API_CONTRACT.md v0.3, D-19, D-21).
//
// Local-only: by default it calls the same origin ("/api/chat"), which the Vite dev
// server forwards to FastAPI at 127.0.0.1:8000, so no CORS is needed. There is no
// mock fallback: any failure is a ChatError, and the UI shows a generic error.
// Error bodies are never read, so server text cannot reach the screen.

import { ChatError, type ChatClient, type ChatOutcome } from "./types";
import { validateChatResponse } from "./validate";

export const CHAT_PATH = "/api/chat";
export const DEFAULT_TIMEOUT_MS = 20_000;
const GATEWAY_STATUSES = new Set([502, 503, 504]);

export interface HttpClientOptions {
  /** Prefix for API paths. Empty (the default) means the same origin as the page. */
  baseUrl?: string;
  timeoutMs?: number;
  fetch?: typeof fetch;
}

function configuredBaseUrl(): string {
  return (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");
}

export function createHttpClient({
  baseUrl = configuredBaseUrl(),
  timeoutMs = DEFAULT_TIMEOUT_MS,
  fetch: fetchImpl = (...args) => globalThis.fetch(...args),
}: HttpClientOptions = {}): ChatClient {
  const url = `${baseUrl}${CHAT_PATH}`;

  return {
    async chat(question: string, signal?: AbortSignal): Promise<ChatOutcome> {
      if (signal?.aborted) throw new ChatError("aborted");
      const controller = new AbortController();
      let timedOut = false;
      const timer = setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, timeoutMs);
      const onAbort = () => controller.abort();
      signal?.addEventListener("abort", onAbort);

      const failure = () => new ChatError(signal?.aborted ? "aborted" : timedOut ? "timeout" : "network");
      try {
        let response: Response;
        try {
          response = await fetchImpl(url, {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify({ question }),
            credentials: "omit",
            cache: "no-store",
            referrerPolicy: "no-referrer",
            signal: controller.signal,
          });
        } catch {
          throw failure();
        }

        // The Vite proxy answers 502 when FastAPI is not running; FastAPI itself never
        // sends these, so they mean the backend could not be reached.
        if (GATEWAY_STATUSES.has(response.status)) throw new ChatError("network");
        if (!response.ok) throw new ChatError("http");
        const contentType = response.headers.get("Content-Type") ?? "";
        if (!/^application\/json\b/i.test(contentType)) throw new ChatError("invalid_response");

        let text: string;
        try {
          text = await response.text();
        } catch {
          throw failure();
        }
        let body: unknown;
        try {
          body = JSON.parse(text);
        } catch {
          throw new ChatError("invalid_response");
        }

        const result = validateChatResponse(body);
        if (result.status === "valid") return { type: "reply", response: result.response };
        if (result.status === "unrecognised") return { type: "unrecognised" };
        throw new ChatError("invalid_response");
      } finally {
        clearTimeout(timer);
        signal?.removeEventListener("abort", onAbort);
      }
    },
  };
}
