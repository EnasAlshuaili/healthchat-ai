import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";
import { createHttpClient } from "./api/httpClient";
import type { ChatClient } from "./api/types";
import { ErrorBoundary } from "./components/ErrorBoundary";
import {
  CURATED_LABEL,
  DISCLAIMER,
  ERROR_HEADINGS,
  LOADING_TEXT,
  MAX_INPUT_CHARS,
  MOCK_LABEL,
  SAFE_FALLBACK_REPLY,
  SAFETY_LABEL,
  SAFETY_NOTICE,
  SERVICE_ERROR,
  SOURCES_HEADING,
  SUGGESTED_QUESTIONS,
} from "./content";
import { contractResponse, curatedResponse, TEMPLATES, TEMPLATE_KEYS, kindOf, type TemplateKey } from "./test/contract";
import { fakeFetch, hangingFetch, jsonResponse } from "./test/server";

const MARKER = "ZZQ-MARKER-7f3a";

type Fetch = ReturnType<typeof vi.fn>;

/** Renders the app with the real HTTP client over a mocked fetch. */
function setup(fetch: Fetch = fakeFetch(() => jsonResponse(contractResponse("mock_answer")))) {
  const user = userEvent.setup();
  render(<App client={createHttpClient({ fetch: fetch as unknown as typeof globalThis.fetch })} />);
  return { user, fetch, input: screen.getByLabelText("Your question") };
}

/** A server that always sends the reply for one template. */
const serving = (key: TemplateKey) => fakeFetch(() => jsonResponse(contractResponse(key)));

/** A fetch whose reply the test releases by hand, to observe the loading state. */
function deferredFetch() {
  const waiting: { resolve: (r: Response) => void; reject: (e: unknown) => void }[] = [];
  const fetch = vi.fn(
    () => new Promise<Response>((resolve, reject) => waiting.push({ resolve, reject })),
  );
  return {
    fetch,
    release: (key: TemplateKey = "mock_answer") => waiting.shift()!.resolve(jsonResponse(contractResponse(key))),
    fail: () => waiting.shift()!.reject(new TypeError("Failed to fetch")),
  };
}

const replies = () => screen.queryAllByRole("article", { name: "QueryMate reply" });

async function ask(user: ReturnType<typeof userEvent.setup>, input: HTMLElement, question = "What is fibre?") {
  await user.type(input, `${question}{Enter}`);
}

describe("initial view", () => {
  it("shows branding, welcome, examples, disclaimer, safety and prototype notices", () => {
    setup();
    expect(screen.getByRole("heading", { level: 1, name: /Hello! I'm QueryMate/ })).toBeInTheDocument();
    expect(screen.getAllByText("QueryMate").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "New chat" })).toBeInTheDocument();
    for (const q of SUGGESTED_QUESTIONS) {
      expect(screen.getByRole("button", { name: q })).toBeInTheDocument();
    }
    expect(screen.getByText(DISCLAIMER, { exact: false })).toBeInTheDocument();
    expect(screen.getAllByText(SAFETY_NOTICE, { exact: false }).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Safety notice" })).toBeInTheDocument();
    expect(screen.getByText(/only a small set of general questions/)).toBeInTheDocument();
    expect(screen.queryByText(/mock placeholder|never an answer/)).not.toBeInTheDocument();
    expect(screen.getByText(/not clinical triage/)).toBeInTheDocument();
    expect(screen.getAllByText("Educational prototype").length).toBeGreaterThan(0);
    expect(screen.queryByRole("list", { name: "Conversation" })).not.toBeInTheDocument();
  });

  it("makes no request until a question is sent", () => {
    const { fetch } = setup();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("does not auto-scroll the welcome screen, but follows the conversation", async () => {
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    const { user, input } = setup();
    expect(scroll).not.toHaveBeenCalled();
    await ask(user, input);
    await screen.findAllByRole("article", { name: "QueryMate reply" });
    expect(scroll).toHaveBeenCalled();
    delete (Element.prototype as Partial<Element>).scrollIntoView;
  });

  it("has an empty input and a disabled send button", () => {
    const { input } = setup();
    expect(input).toHaveValue("");
    expect(screen.getByRole("button", { name: "Send question" })).toBeDisabled();
  });

  it("makes no claim of clinical validation", () => {
    setup();
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/\b(is|are|been) clinically (validated|approved|verified)/i);
    expect(text).not.toMatch(/doctor-approved|verified answer/i);
  });
});

describe("example questions", () => {
  it("sends the selected example and shows the server's labelled mock reply", async () => {
    const { user, fetch } = setup();
    await user.click(screen.getByRole("button", { name: SUGGESTED_QUESTIONS[1] }));
    const conversation = await screen.findByRole("list", { name: "Conversation" });
    expect(within(conversation).getByText(SUGGESTED_QUESTIONS[1])).toBeInTheDocument();
    const [reply] = await screen.findAllByRole("article", { name: "QueryMate reply" });
    expect(within(reply).getByText(MOCK_LABEL)).toBeInTheDocument();
    expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({ question: SUGGESTED_QUESTIONS[1] });
    expect(screen.queryByRole("heading", { name: /Hello! I'm QueryMate/ })).not.toBeInTheDocument();
  });
});

describe("message submission", () => {
  it("sends with Enter, clears the input, and shows the mock label", async () => {
    const { user, input } = setup();
    await ask(user, input, "What is good sleep hygiene?");
    expect(input).toHaveValue("");
    const [reply] = await screen.findAllByRole("article", { name: "QueryMate reply" });
    expect(within(reply).getByText(MOCK_LABEL)).toBeInTheDocument();
    expect(within(reply).getByText(/^Mock response: answers are not available yet$/)).toBeInTheDocument();
  });

  it("sends with the send button", async () => {
    const { user, input } = setup();
    await user.type(input, "What does a balanced diet include?");
    await user.click(screen.getByRole("button", { name: "Send question" }));
    expect(await screen.findAllByRole("article", { name: "QueryMate reply" })).toHaveLength(1);
  });

  it("Shift+Enter adds a new line instead of sending", async () => {
    const { user, input, fetch } = setup();
    await user.type(input, "line one{Shift>}{Enter}{/Shift}line two");
    expect(input).toHaveValue("line one\nline two");
    expect(screen.queryByRole("list", { name: "Conversation" })).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("does not send whitespace-only input", async () => {
    const { user, input, fetch } = setup();
    await user.type(input, "   {Enter}");
    expect(screen.getByRole("button", { name: "Send question" })).toBeDisabled();
    expect(screen.queryByRole("list", { name: "Conversation" })).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("shows the same server reply identically and never echoes the question in it", async () => {
    const { user, input } = setup();
    await ask(user, input, `What is ${MARKER}?`);
    await screen.findAllByRole("article", { name: "QueryMate reply" });
    await ask(user, input, "What is fibre?");
    await waitFor(() => expect(replies()).toHaveLength(2));
    const [first, second] = replies();
    expect(first.textContent).toBe(second.textContent);
    expect(first.textContent).not.toContain(MARKER);
  });

  it("renders user text as plain text, not HTML", async () => {
    const { user, input } = setup();
    await ask(user, input, "<b>bold</b> <img src=x>");
    expect(await screen.findByText("<b>bold</b> <img src=x>")).toBeInTheDocument();
    expect(document.querySelector("main b, main img")).toBeNull();
  });

  it("renders server text as plain text, not HTML", async () => {
    const body = contractResponse("mock_answer");
    body.message.paragraphs = ["<img src=x onerror=alert(1)> <b>bold</b>"];
    const { user, input } = setup(fakeFetch(() => jsonResponse(body)));
    await ask(user, input);
    expect(await screen.findByText("<img src=x onerror=alert(1)> <b>bold</b>")).toBeInTheDocument();
    expect(document.querySelector("main b, main img")).toBeNull();
  });

  it("warns softly over 1,000 characters but still sends; the server decides", async () => {
    const { user, input, fetch } = setup(serving("invalid_input:too_long"));
    await user.click(input);
    await user.paste("a".repeat(MAX_INPUT_CHARS + 1));
    expect(screen.getByText(/usually can't be answered\. You can still send it\./)).toBeInTheDocument();
    const send = screen.getByRole("button", { name: "Send question" });
    expect(send).toBeEnabled();
    await user.click(send);
    const [reply] = await screen.findAllByRole("article", { name: "QueryMate reply" });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(within(reply).getByText("Your question is too long.")).toBeInTheDocument();
    expect(within(reply).queryByText(MOCK_LABEL)).not.toBeInTheDocument();
  });

  it("blocks sending over the 20,000-character scan limit", async () => {
    const { user, input, fetch } = setup();
    await user.click(input);
    await user.paste("a".repeat(20_001));
    expect(screen.getByText(/too long to send/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send question" })).toBeDisabled();
    await user.keyboard("{Enter}");
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe("curated answers (contract v0.3)", () => {
  const servingCurated = () => fakeFetch(() => jsonResponse(curatedResponse()));

  it("renders the exact title and paragraphs with the owner-review label", async () => {
    const { user, input } = setup(servingCurated());
    await ask(user, input, SUGGESTED_QUESTIONS[0]);
    const [reply] = await screen.findAllByRole("article", { name: "QueryMate reply" });
    const { title, paragraphs } = curatedResponse().message;
    expect(within(reply).getByText(title)).toBeInTheDocument();
    const rendered = [...reply.querySelectorAll("p")].map((p) => p.textContent);
    const start = rendered.indexOf(paragraphs[0]);
    expect(rendered.slice(start, start + paragraphs.length)).toEqual(paragraphs);
    expect(within(reply).getByText(CURATED_LABEL)).toBeInTheDocument();
    expect(within(reply).queryByText(MOCK_LABEL)).not.toBeInTheDocument();
    expect(within(reply).queryByText(SAFETY_LABEL)).not.toBeInTheDocument();
    expect(within(reply).queryByRole("alert")).not.toBeInTheDocument();
  });

  it("lists every source with its organization and a safe https link", async () => {
    const { user, input } = setup(servingCurated());
    await ask(user, input, SUGGESTED_QUESTIONS[0]);
    const [reply] = await screen.findAllByRole("article", { name: "QueryMate reply" });
    const section = within(reply).getByRole("region", { name: SOURCES_HEADING });
    const { sources } = curatedResponse();
    expect(within(section).getAllByRole("link")).toHaveLength(sources.length);
    for (const source of sources) {
      const link = within(section).getByRole("link", { name: source.title });
      expect(link).toHaveAttribute("href", source.url);
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
      expect(link.closest("li")).toHaveTextContent(source.organization);
    }
  });

  it("renders source text as plain text, not HTML", async () => {
    const body = curatedResponse();
    body.sources = [{ title: "<b>bold</b>", organization: "<img src=x>", url: "https://example.org/" }];
    const { user, input } = setup(fakeFetch(() => jsonResponse(body)));
    await ask(user, input);
    expect(await screen.findByRole("link", { name: "<b>bold</b>" })).toBeInTheDocument();
    expect(document.querySelector("main b, main img")).toBeNull();
  });

  it("makes no claim of clinical review or validation", async () => {
    const { user, input } = setup(servingCurated());
    await ask(user, input, SUGGESTED_QUESTIONS[0]);
    await screen.findAllByRole("article", { name: "QueryMate reply" });
    // Every use of "clinically" must be one of the required negative statements.
    const text = (document.body.textContent ?? "").replace(/not (been )?clinically reviewed( or (clinically )?validated)?/gi, "");
    expect(text).not.toMatch(/clinically|medically approved|doctor-approved|verified answer/i);
  });

  it.each(TEMPLATE_KEYS)("shows no sources or links on %s", async (key) => {
    const { user, input } = setup(serving(key));
    await ask(user, input);
    const [reply] = await screen.findAllByRole("article", { name: "QueryMate reply" });
    expect(within(reply).queryByRole("region", { name: SOURCES_HEADING })).not.toBeInTheDocument();
    expect(within(reply).queryByRole("link")).not.toBeInTheDocument();
    expect(within(reply).queryByText(CURATED_LABEL)).not.toBeInTheDocument();
  });

  it.each<[string, () => Record<string, unknown>]>([
    ["a safety reply carrying sources", () => ({ ...contractResponse("emergency"), sources: curatedResponse().sources })],
    ["a curated answer without sources", () => ({ ...curatedResponse(), sources: [] })],
    ["a curated answer with a script link", () => {
      const body = curatedResponse();
      body.sources[0].url = "javascript:alert(1)";
      return body as unknown as Record<string, unknown>;
    }],
    ["a pending curated answer", () => ({ ...curatedResponse(), review_status: "pending_owner_review" })],
  ])("shows a generic error, and none of its text, for %s", async (_name, body) => {
    const { user, input } = setup(fakeFetch(() => jsonResponse(body())));
    await ask(user, input);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(ERROR_HEADINGS.unreadable);
    expect(replies()).toHaveLength(0);
    expect(screen.queryByRole("link", { name: curatedResponse().sources[1].title })).not.toBeInTheDocument();
  });
});

describe("server replies (contract v0.3)", () => {
  it.each(TEMPLATE_KEYS)("renders %s with the exact approved title and paragraphs, in order", async (key) => {
    const { user, input } = setup(serving(key));
    await ask(user, input);
    const [reply] = await screen.findAllByRole("article", { name: "QueryMate reply" });
    const { title, paragraphs } = TEMPLATES[key];
    expect(within(reply).getByText(title)).toBeInTheDocument();
    const rendered = [...reply.querySelectorAll("p")].map((p) => p.textContent);
    const start = rendered.indexOf(paragraphs[0]);
    expect(start).toBeGreaterThanOrEqual(0);
    expect(rendered.slice(start, start + paragraphs.length)).toEqual(paragraphs);
  });

  it.each(TEMPLATE_KEYS)("labels %s by is_mock and content_source", async (key) => {
    const { user, input } = setup(serving(key));
    await ask(user, input);
    const [reply] = await screen.findAllByRole("article", { name: "QueryMate reply" });
    const kind = kindOf(key);
    const mock = within(reply).queryByText(MOCK_LABEL);
    const safety = within(reply).queryByText(SAFETY_LABEL);
    if (kind === "mock_answer") {
      expect(mock).toBeInTheDocument();
      expect(safety).not.toBeInTheDocument();
    } else if (kind === "invalid_input") {
      expect(mock).not.toBeInTheDocument();
      expect(safety).not.toBeInTheDocument();
    } else {
      expect(mock).not.toBeInTheDocument();
      expect(safety).toBeInTheDocument();
    }
    expect(reply.textContent).not.toMatch(/reviewed|validated|verified|doctor-approved/i);
  });

  it("shows a router-null safe fallback exactly like any other safe fallback", async () => {
    const { user, input } = setup(fakeFetch(() => jsonResponse(contractResponse("safe_fallback", null))));
    await ask(user, input);
    const [reply] = await screen.findAllByRole("article", { name: "QueryMate reply" });
    expect(within(reply).getByText(TEMPLATES.safe_fallback.title)).toBeInTheDocument();
    expect(within(reply).getByText(SAFETY_LABEL)).toBeInTheDocument();
  });
});

describe("emergency and crisis replies", () => {
  it.each(["emergency", "crisis"] as const)("shows %s first, as an alert with an icon and a heading", async (key) => {
    const { user, input } = setup(serving(key));
    await ask(user, input, "I have chest pain");
    const [reply] = await screen.findAllByRole("article", { name: "QueryMate reply" });
    const { title, paragraphs } = TEMPLATES[key];

    const alert = within(reply).getByRole("alert");
    const heading = within(alert).getByRole("heading", { level: 2, name: title });
    expect(heading.querySelector("svg")).not.toBeNull(); // icon, not colour alone
    expect([...alert.querySelectorAll("p")].map((p) => p.textContent)).toEqual(paragraphs);
    expect(alert.textContent).toBe(title + paragraphs.join(""));

    // The guidance comes before the label, and nothing hides it.
    const label = within(reply).getByText(SAFETY_LABEL);
    expect(alert.compareDocumentPosition(label) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(reply.querySelector("details, dialog, [hidden], [aria-hidden='true'] p")).toBeNull();
    expect(within(reply).queryByRole("button")).not.toBeInTheDocument();
    expect(within(reply).queryByText(MOCK_LABEL)).not.toBeInTheDocument();
    expect(alert).toBeVisible();

    // The disclaimer and safety notice stay visible alongside it.
    expect(screen.getByText(DISCLAIMER, { exact: false })).toBeVisible();
    expect(screen.getAllByText(SAFETY_NOTICE, { exact: false }).length).toBeGreaterThan(0);
  });

  it("does not present other replies as alerts", async () => {
    for (const key of TEMPLATE_KEYS.filter((k) => k !== "emergency" && k !== "crisis")) {
      const { user, input } = setup(serving(key));
      await ask(user, input);
      const [reply] = await screen.findAllByRole("article", { name: "QueryMate reply" });
      expect(within(reply).queryByRole("alert"), key).not.toBeInTheDocument();
      cleanup();
    }
  });
});

describe("unrecognised and malformed replies", () => {
  it("treats an unknown kind as the approved safe fallback and never shows its text", async () => {
    const body = { ...contractResponse("mock_answer"), kind: "medical_advice", is_mock: false };
    body.message = { title: `SERVER-TITLE ${MARKER}`, paragraphs: ["Take 400 mg"] };
    const { user, input } = setup(fakeFetch(() => jsonResponse(body)));
    await ask(user, input);
    const [reply] = await screen.findAllByRole("article", { name: "QueryMate reply" });
    expect(within(reply).getByText(SAFE_FALLBACK_REPLY.title)).toBeInTheDocument();
    for (const paragraph of SAFE_FALLBACK_REPLY.paragraphs) expect(within(reply).getByText(paragraph)).toBeInTheDocument();
    expect(within(reply).getByText(SAFETY_LABEL)).toBeInTheDocument();
    expect(document.body.textContent).not.toContain(MARKER);
    expect(document.body.textContent).not.toContain("400 mg");
  });

  it("treats the reserved reviewed_content source as the safe fallback", async () => {
    const body = { ...contractResponse("mock_answer"), content_source: "reviewed_content" };
    const { user, input } = setup(fakeFetch(() => jsonResponse(body)));
    await ask(user, input);
    const [reply] = await screen.findAllByRole("article", { name: "QueryMate reply" });
    expect(within(reply).getByText(SAFE_FALLBACK_REPLY.title)).toBeInTheDocument();
    expect(within(reply).queryByText(MOCK_LABEL)).not.toBeInTheDocument();
  });

  it.each<[string, () => Response]>([
    ["invalid JSON", () => jsonResponse("{not json")],
    ["a missing field", () => jsonResponse({ ...contractResponse("emergency"), disclaimer: undefined })],
    ["mismatched metadata", () => jsonResponse({ ...contractResponse("emergency"), is_mock: true })],
    ["a non-JSON body", () => jsonResponse(`<html>${MARKER}</html>`, 200, "text/html")],
  ])("shows a generic error for %s, without the server's text", async (_name, reply) => {
    const { user, input } = setup(fakeFetch(reply));
    await ask(user, input);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(ERROR_HEADINGS.unreadable);
    expect(alert).toHaveTextContent(SERVICE_ERROR);
    expect(replies()).toHaveLength(0);
    expect(document.body.textContent).not.toContain(MARKER);
    expect(screen.queryByText(TEMPLATES.emergency.title)).not.toBeInTheDocument();
  });
});

describe("loading and error states", () => {
  it("shows a loading state and disables sending while waiting", async () => {
    const d = deferredFetch();
    const { user, input } = setup(d.fetch);
    await ask(user, input);
    expect(screen.getByRole("status")).toHaveTextContent(LOADING_TEXT);
    await user.type(input, "next");
    expect(screen.getByRole("button", { name: "Send question" })).toBeDisabled();
    d.release();
    await screen.findAllByRole("article", { name: "QueryMate reply" });
    expect(screen.queryByText(LOADING_TEXT)).not.toBeInTheDocument();
  });

  it("sends only one request however often the user submits while waiting", async () => {
    const d = deferredFetch();
    const { user, input } = setup(d.fetch);
    await user.type(input, "What is fibre?");
    const send = screen.getByRole("button", { name: "Send question" });
    await user.dblClick(send);
    await user.type(input, "again{Enter}{Enter}");
    await user.click(send);
    expect(d.fetch).toHaveBeenCalledTimes(1);
    d.release();
    expect(await screen.findAllByRole("article", { name: "QueryMate reply" })).toHaveLength(1);
  });

  it("ignores a second submit in the same tick, before React re-renders", async () => {
    const d = deferredFetch();
    const { user, input } = setup(d.fetch);
    await user.type(input, "What is fibre?");
    const form = input.closest("form")!;
    act(() => {
      fireEvent.submit(form);
      fireEvent.submit(form);
    });
    expect(d.fetch).toHaveBeenCalledTimes(1);
    d.release();
    expect(await screen.findAllByRole("article", { name: "QueryMate reply" })).toHaveLength(1);
    expect(screen.getAllByText("What is fibre?")).toHaveLength(1);
  });

  it("sends one request per question under React Strict Mode", async () => {
    const fetch = fakeFetch(() => jsonResponse(contractResponse("mock_answer")));
    const user = userEvent.setup();
    render(
      <StrictMode>
        <App client={createHttpClient({ fetch })} />
      </StrictMode>,
    );
    await ask(user, screen.getByLabelText("Your question"));
    await screen.findAllByRole("article", { name: "QueryMate reply" });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("shows 'could not be reached' with the emergency line when the backend is down, and no mock reply", async () => {
    const d = deferredFetch();
    const { user, input } = setup(d.fetch);
    await ask(user, input, `What is ${MARKER}?`);
    d.fail();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(ERROR_HEADINGS.unreachable);
    expect(alert).toHaveTextContent(SERVICE_ERROR);
    expect(alert).toHaveTextContent(/emergency services/);
    expect(alert).not.toHaveTextContent(MARKER);
    expect(replies()).toHaveLength(0);
    expect(screen.queryByText(MOCK_LABEL)).not.toBeInTheDocument();
    expect(screen.queryByText(TEMPLATES.mock_answer.title)).not.toBeInTheDocument();

    await ask(user, input, "Try again");
    d.release();
    expect(await screen.findAllByRole("article", { name: "QueryMate reply" })).toHaveLength(1);
  });

  it("shows 'could not be reached' when the dev proxy reports the backend down (502)", async () => {
    const { user, input } = setup(fakeFetch(() => new Response("", { status: 502, headers: { "Content-Type": "text/plain" } })));
    await ask(user, input);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(ERROR_HEADINGS.unreachable);
    expect(alert).toHaveTextContent(SERVICE_ERROR);
    expect(screen.queryByText(MOCK_LABEL)).not.toBeInTheDocument();
  });

  it.each([500, 422, 413])("shows a generic 'unavailable' error for HTTP %i, without the server's message", async (code) => {
    const envelope = { error: { code: "internal_error", message: `server says ${MARKER}`, request_id: "r" } };
    const { user, input } = setup(fakeFetch(() => jsonResponse(envelope, code)));
    await ask(user, input);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(ERROR_HEADINGS.unavailable);
    expect(alert).toHaveTextContent(SERVICE_ERROR);
    expect(document.body.textContent).not.toContain(MARKER);
    expect(screen.queryByText(MOCK_LABEL)).not.toBeInTheDocument();
  });

  it("shows 'could not be reached' after a timeout", async () => {
    const user = userEvent.setup();
    render(<App client={createHttpClient({ fetch: hangingFetch(), timeoutMs: 5 })} />);
    await ask(user, screen.getByLabelText("Your question"));
    expect(await screen.findByRole("alert")).toHaveTextContent(ERROR_HEADINGS.unreachable);
  });

  it("shows 'something went wrong' for an unexpected client error", async () => {
    const client: ChatClient = {
      chat: async () => {
        throw new RangeError(`internal detail ${MARKER}`);
      },
    };
    const user = userEvent.setup();
    render(<App client={client} />);
    await ask(user, screen.getByLabelText("Your question"));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(ERROR_HEADINGS.unexpected);
    expect(alert).toHaveTextContent(SERVICE_ERROR);
    expect(document.body.textContent).not.toContain(MARKER);
  });

  it("keeps the disclaimer visible in every error state", async () => {
    const { user, input } = setup(fakeFetch(() => jsonResponse("", 500)));
    await ask(user, input);
    await screen.findByRole("alert");
    expect(screen.getByText(DISCLAIMER, { exact: false })).toBeVisible();
  });
});

describe("rendering failures", () => {
  it("shows the service error, safety notice, and disclaimer instead of a blank page", () => {
    const silence = vi.spyOn(console, "error").mockImplementation(() => {});
    function Broken(): never {
      throw new Error(`render failure ${MARKER}`);
    }
    render(
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(SERVICE_ERROR);
    expect(screen.getByText(SAFETY_NOTICE, { exact: false })).toBeInTheDocument();
    expect(screen.getByText(DISCLAIMER)).toBeInTheDocument();
    expect(document.body.textContent).not.toContain(MARKER);
    silence.mockRestore();
  });
});

describe("new chat", () => {
  it("clears the conversation and returns to the welcome screen", async () => {
    const { user, input } = setup();
    await ask(user, input);
    await screen.findAllByRole("article", { name: "QueryMate reply" });
    await user.click(screen.getByRole("button", { name: "New chat" }));
    expect(screen.getByRole("heading", { name: /Hello! I'm QueryMate/ })).toBeInTheDocument();
    expect(replies()).toHaveLength(0);
  });

  it("cancels the request in progress and discards a reply that arrives afterwards", async () => {
    const d = deferredFetch();
    const { user, input } = setup(d.fetch);
    await ask(user, input);
    const signal = (d.fetch.mock.calls[0] as unknown as [string, RequestInit])[1].signal!;
    await user.click(screen.getByRole("button", { name: "New chat" }));
    expect(signal.aborted).toBe(true);
    d.release("emergency");
    await new Promise((r) => setTimeout(r, 0));
    expect(replies()).toHaveLength(0);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Hello! I'm QueryMate/ })).toBeInTheDocument();
  });

  it("can send again right after New chat", async () => {
    const d = deferredFetch();
    const { user, input } = setup(d.fetch);
    await ask(user, input);
    await user.click(screen.getByRole("button", { name: "New chat" }));
    await ask(user, input, "Second question");
    expect(d.fetch).toHaveBeenCalledTimes(2);
    d.release(); // the first, discarded
    d.release("crisis");
    const [reply] = await screen.findAllByRole("article", { name: "QueryMate reply" });
    expect(within(reply).getByText(TEMPLATES.crisis.title)).toBeInTheDocument();
    expect(replies()).toHaveLength(1);
  });
});

describe("navigation and menu", () => {
  it("shows the About view with the prototype notice", async () => {
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "About" }));
    expect(screen.getByRole("heading", { level: 1, name: "About QueryMate" })).toBeInTheDocument();
    expect(screen.getByText(/has not been clinically reviewed or validated/)).toBeInTheDocument();
    expect(screen.getByText(/Limited to one topic\./)).toBeInTheDocument();
    expect(screen.queryByText(/mock placeholder/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "About" })).toHaveAttribute("aria-current", "page");
  });

  it("opens and closes the mobile menu with Escape, returning focus", async () => {
    const { user } = setup();
    const open = screen.getByRole("button", { name: "Open menu" });
    await user.click(open);
    expect(screen.getByRole("dialog", { name: "Menu" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Menu" })).not.toBeInTheDocument();
    expect(open).toHaveFocus();
  });
});

describe("network and privacy", () => {
  it("the default client calls only the same-origin /api/chat, once per question", async () => {
    const fetch = fakeFetch(() => jsonResponse(contractResponse("mock_answer")));
    vi.stubGlobal("fetch", fetch);
    const user = userEvent.setup();
    render(<App />); // the app's own default client
    expect(fetch).not.toHaveBeenCalled();
    await ask(user, screen.getByLabelText("Your question"));
    await screen.findAllByRole("article", { name: "QueryMate reply" });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toBe("/api/chat");
    vi.unstubAllGlobals();
  });

  it("stores no questions or replies in browser storage or cookies", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const { user, input } = setup(serving("crisis"));
    await ask(user, input, `What is ${MARKER}?`);
    await screen.findAllByRole("article", { name: "QueryMate reply" });
    expect(setItem).not.toHaveBeenCalled();
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
    expect(document.cookie).toBe("");
  });

  it("makes no claim of clinical validation after any reply", async () => {
    for (const key of TEMPLATE_KEYS) {
      const { user, input } = setup(serving(key));
      await ask(user, input);
      await screen.findAllByRole("article", { name: "QueryMate reply" });
      const text = document.body.textContent ?? "";
      expect(text, key).not.toMatch(/\b(is|are|been) clinically (validated|approved|verified)/i);
      expect(text, key).not.toMatch(/doctor-approved|verified answer|reviewed content/i);
      cleanup();
    }
  });
});
