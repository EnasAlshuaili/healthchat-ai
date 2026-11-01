// Mocked HTTP for tests: a fake fetch that answers /api/chat like the server would.
import { vi } from "vitest";

export function jsonResponse(body: unknown, status = 200, contentType = "application/json"): Response {
  return new Response(typeof body === "string" ? body : JSON.stringify(body), {
    status,
    headers: { "Content-Type": contentType, "Cache-Control": "no-store" },
  });
}

/** Builds a fetch stub; `reply` decides the response from the question that was sent. */
export function fakeFetch(reply: (question: string) => Response | Promise<Response>) {
  return vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
    const { question } = JSON.parse(String(init?.body)) as { question: string };
    return reply(question);
  });
}

/** A fetch that never answers until the request is aborted (then rejects like a browser). */
export function hangingFetch() {
  return vi.fn(
    (_url: RequestInfo | URL, init?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      }),
  );
}
