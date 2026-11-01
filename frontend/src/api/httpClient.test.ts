import { afterEach, describe, expect, it, vi } from "vitest";
import { contractResponse, TEMPLATE_KEYS } from "../test/contract";
import { fakeFetch, hangingFetch, jsonResponse } from "../test/server";
import { CHAT_PATH, createHttpClient } from "./httpClient";
import { ChatError } from "./types";

const MARKER = "ZZQ-MARKER-7f3a";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

async function failure(promise: Promise<unknown>): Promise<ChatError> {
  try {
    await promise;
  } catch (error) {
    expect(error).toBeInstanceOf(ChatError);
    return error as ChatError;
  }
  throw new Error("expected the request to fail");
}

describe("request", () => {
  it("POSTs exactly {question} as JSON to the same-origin /api/chat", async () => {
    const fetch = fakeFetch(() => jsonResponse(contractResponse("mock_answer")));
    await createHttpClient({ fetch }).chat("Why is staying hydrated important?");
    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("/api/chat");
    expect(CHAT_PATH).toBe("/api/chat");
    expect(init?.method).toBe("POST");
    expect(init?.headers).toEqual({ "Content-Type": "application/json", Accept: "application/json" });
    expect(init?.body).toBe('{"question":"Why is staying hydrated important?"}');
    expect(init?.credentials).toBe("omit");
    expect(init?.cache).toBe("no-store");
    expect(init?.referrerPolicy).toBe("no-referrer");
    expect(init?.signal).toBeInstanceOf(AbortSignal);
  });

  it("sends the question unchanged (no trimming, no client-side safety logic)", async () => {
    const fetch = fakeFetch(() => jsonResponse(contractResponse("mock_answer")));
    const question = "  I have chest pain\n\t😀 <b>x</b>  ";
    await createHttpClient({ fetch }).chat(question);
    expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({ question });
  });

  it("uses VITE_API_BASE_URL when set, without a trailing slash", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://127.0.0.1:8000/");
    const fetch = fakeFetch(() => jsonResponse(contractResponse("mock_answer")));
    await createHttpClient({ fetch }).chat("q");
    expect(fetch.mock.calls[0][0]).toBe("http://127.0.0.1:8000/api/chat");
  });

  it("uses the global fetch by default, still same-origin", async () => {
    const fetch = fakeFetch(() => jsonResponse(contractResponse("mock_answer")));
    vi.stubGlobal("fetch", fetch);
    await createHttpClient().chat("q");
    expect(fetch.mock.calls[0][0]).toBe("/api/chat");
  });
});

describe("successful replies", () => {
  it("returns every contract reply unchanged", async () => {
    for (const key of TEMPLATE_KEYS) {
      const body = contractResponse(key);
      const outcome = await createHttpClient({ fetch: fakeFetch(() => jsonResponse(body)) }).chat("q");
      expect(outcome, key).toEqual({ type: "reply", response: body });
    }
  });

  it("accepts a JSON content type with a charset", async () => {
    const fetch = fakeFetch(() => jsonResponse(contractResponse("crisis"), 200, "application/json; charset=utf-8"));
    expect((await createHttpClient({ fetch }).chat("q")).type).toBe("reply");
  });

  it("reports an unknown kind as unrecognised, without its text", async () => {
    const body = { ...contractResponse("safe_fallback"), kind: "new_kind" };
    const outcome = await createHttpClient({ fetch: fakeFetch(() => jsonResponse(body)) }).chat("q");
    expect(outcome).toEqual({ type: "unrecognised" });
  });
});

describe("failures are errors, never mock answers", () => {
  it("network failure", async () => {
    const fetch = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    const error = await failure(createHttpClient({ fetch }).chat(`What is ${MARKER}?`));
    expect(error.kind).toBe("network");
    expect(error.message).not.toContain(MARKER);
    expect(error.message).not.toContain("Failed to fetch");
  });

  it.each([
    [400, "http"],
    [404, "http"],
    [405, "http"],
    [413, "http"],
    [415, "http"],
    [422, "http"],
    [500, "http"],
    [502, "network"], // the Vite proxy's answer when FastAPI is not running
    [503, "network"],
    [504, "network"],
  ])("HTTP %i is a %s error, and the body is not read", async (code, kind) => {
    const response = jsonResponse({ error: { code: "internal_error", message: "server text", request_id: "x" } }, code);
    const text = vi.spyOn(response, "text");
    const json = vi.spyOn(response, "json");
    const error = await failure(createHttpClient({ fetch: vi.fn(async () => response) }).chat("q"));
    expect(error.kind).toBe(kind);
    expect(text).not.toHaveBeenCalled();
    expect(json).not.toHaveBeenCalled();
  });

  it("a non-JSON content type", async () => {
    const fetch = fakeFetch(() => jsonResponse(contractResponse("mock_answer"), 200, "text/html"));
    expect((await failure(createHttpClient({ fetch }).chat("q"))).kind).toBe("invalid_response");
  });

  it.each(["", "not json", "{", "null", "[]", '"text"'])("an invalid or non-object JSON body %j", async (text) => {
    const fetch = fakeFetch(() => jsonResponse(text));
    expect((await failure(createHttpClient({ fetch }).chat("q"))).kind).toBe("invalid_response");
  });

  it("a body that breaks the contract", async () => {
    const body = { ...contractResponse("emergency"), is_mock: true };
    const fetch = fakeFetch(() => jsonResponse(body));
    expect((await failure(createHttpClient({ fetch }).chat("q"))).kind).toBe("invalid_response");
  });

  it("a v0.1 body (the superseded mock contract)", async () => {
    const v01 = { ...contractResponse("mock_answer"), api_version: "0.1", versions: { router: null, matcher: null, content: "mock" } };
    delete (v01 as Partial<typeof v01>).content_source;
    expect((await failure(createHttpClient({ fetch: fakeFetch(() => jsonResponse(v01)) }).chat("q"))).kind).toBe(
      "invalid_response",
    );
  });

  it("a timeout", async () => {
    const error = await failure(createHttpClient({ fetch: hangingFetch(), timeoutMs: 5 }).chat("q"));
    expect(error.kind).toBe("timeout");
  });

  it("cancellation by the caller", async () => {
    const controller = new AbortController();
    const pending = createHttpClient({ fetch: hangingFetch() }).chat("q", controller.signal);
    controller.abort();
    expect((await failure(pending)).kind).toBe("aborted");
  });

  it("an already-cancelled request makes no call", async () => {
    const fetch = hangingFetch();
    const controller = new AbortController();
    controller.abort();
    expect((await failure(createHttpClient({ fetch }).chat("q", controller.signal))).kind).toBe("aborted");
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe("privacy", () => {
  it("stores nothing in browser storage or cookies", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const fetch = fakeFetch(() => jsonResponse(contractResponse("mock_answer")));
    await createHttpClient({ fetch }).chat(`What is ${MARKER}?`);
    expect(setItem).not.toHaveBeenCalled();
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
    expect(document.cookie).toBe("");
  });
});
