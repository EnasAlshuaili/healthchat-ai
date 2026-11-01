// Chat bubbles. All text is rendered as plain React text: never as HTML or Markdown
// (API_CONTRACT "Frontend obligations"). Reply wording comes from the server and is
// shown unchanged; the only local reply is the approved safe_fallback text, used when
// the server's kind or content_source is not recognised.
import type { ChatResponse, ReplyMessage, Source } from "../api/types";
import {
  ERROR_HEADINGS,
  LOADING_TEXT,
  SAFE_FALLBACK_REPLY,
  SERVICE_ERROR,
  SOURCES_HEADING,
  type ErrorState,
} from "../content";
import { CuratedBadge, MockBadge, SafetyBadge } from "./Badges";
import { AlertIcon, BotIcon, UserIcon } from "./Icons";

export type Entry =
  | { id: number; role: "user"; text: string }
  | { id: number; role: "assistant"; response: ChatResponse }
  | { id: number; role: "fallback" }
  | { id: number; role: "error"; state: ErrorState };

const URGENT_KINDS: ReadonlySet<ChatResponse["kind"]> = new Set(["emergency", "crisis"]);

function AssistantAvatar() {
  return (
    <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-tint text-primary ring-1 ring-line">
      <BotIcon className="size-5" />
    </span>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex items-start justify-end gap-2">
      <div className="max-w-[85%] rounded-2xl rounded-tr-md bg-primary px-4 py-2 text-white shadow-sm">
        <span className="sr-only">You asked: </span>
        <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">{text}</p>
      </div>
      <span className="hidden size-8 shrink-0 items-center justify-center rounded-full bg-tint-strong text-primary-strong sm:flex">
        <UserIcon className="size-5" />
      </span>
    </div>
  );
}

function Paragraphs({ message }: { message: ReplyMessage }) {
  return (
    <div className="mt-2 space-y-2 text-sm leading-relaxed">
      {message.paragraphs.map((paragraph, i) => (
        <p key={i}>{paragraph}</p>
      ))}
    </div>
  );
}

/** Sources of a curated answer: plain text with https links (checked by the validator). */
function Sources({ sources }: { sources: readonly Source[] }) {
  return (
    <section aria-label={SOURCES_HEADING} className="mt-3 border-t border-line pt-2 text-xs leading-relaxed">
      <p className="font-semibold">{SOURCES_HEADING}</p>
      <ul className="mt-1 space-y-1">
        {sources.map((source) => (
          <li key={source.url}>
            <a className="underline" href={source.url} target="_blank" rel="noopener noreferrer">
              {source.title}
            </a>{" "}
            ({source.organization})
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * Emergency and crisis replies: the guidance comes first, under an icon and a text
 * heading (never colour alone), inside an alert so screen readers announce it at once.
 */
function UrgentBubble({ message }: { message: ReplyMessage }) {
  return (
    <div className="flex items-start gap-2">
      <AssistantAvatar />
      <article
        aria-label="HealthChat AI reply"
        data-urgent="true"
        className="min-w-0 rounded-2xl rounded-tl-md border-2 border-red-400 bg-red-50 px-4 py-3 text-red-950 shadow-sm sm:max-w-[85%]"
      >
        <div role="alert">
          <h2 className="flex items-start gap-2 text-base font-bold">
            <AlertIcon className="mt-0.5 size-5 shrink-0 text-red-700" />
            {message.title}
          </h2>
          <Paragraphs message={message} />
        </div>
        <div className="mt-3">
          <SafetyBadge />
        </div>
      </article>
    </div>
  );
}

type Badge = "curated" | "mock" | "safety" | null;

function ReplyBubble({
  message,
  badge,
  invalid = false,
  sources = [],
}: {
  message: ReplyMessage;
  badge: Badge;
  invalid?: boolean;
  sources?: readonly Source[];
}) {
  return (
    <div className="flex items-start gap-2">
      <AssistantAvatar />
      <article
        aria-label="HealthChat AI reply"
        className={`min-w-0 rounded-2xl rounded-tl-md border px-4 py-3 shadow-sm sm:max-w-[85%] ${
          invalid ? "border-amber-300 bg-amber-50 text-amber-950" : "border-line bg-white"
        }`}
      >
        {badge && (
          <div className="mb-2">
            {badge === "curated" ? <CuratedBadge /> : badge === "mock" ? <MockBadge /> : <SafetyBadge />}
          </div>
        )}
        <p className="flex items-start gap-2 text-sm font-semibold">
          {invalid && <AlertIcon className="mt-0.5 size-4 shrink-0 text-amber-700" />}
          {message.title}
        </p>
        <Paragraphs message={message} />
        {sources.length > 0 && <Sources sources={sources} />}
      </article>
    </div>
  );
}

function AssistantBubble({ response }: { response: ChatResponse }) {
  if (URGENT_KINDS.has(response.kind)) return <UrgentBubble message={response.message} />;
  if (response.kind === "curated_answer") {
    return <ReplyBubble message={response.message} badge="curated" sources={response.sources} />;
  }
  const badge = response.is_mock ? "mock" : response.content_source === "safety_template" ? "safety" : null;
  return <ReplyBubble message={response.message} badge={badge} invalid={response.kind === "invalid_input"} />;
}

const fallbackMessage: ReplyMessage = {
  title: SAFE_FALLBACK_REPLY.title,
  paragraphs: [...SAFE_FALLBACK_REPLY.paragraphs],
};

function ErrorBubble({ state }: { state: ErrorState }) {
  return (
    <div className="flex items-start gap-2">
      <AssistantAvatar />
      <div
        role="alert"
        className="min-w-0 rounded-2xl rounded-tl-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900 sm:max-w-[85%]"
      >
        <p className="flex items-center gap-2 font-semibold">
          <AlertIcon className="size-4 text-red-700" />
          {ERROR_HEADINGS[state]}
        </p>
        <p className="mt-1.5 leading-relaxed">{SERVICE_ERROR}</p>
      </div>
    </div>
  );
}

export function LoadingBubble() {
  return (
    <div className="flex items-start gap-2">
      <AssistantAvatar />
      <div
        role="status"
        className="flex items-center gap-3 rounded-2xl rounded-tl-md border border-line bg-white px-4 py-2 text-sm text-muted shadow-sm"
      >
        <span className="flex gap-1" aria-hidden="true">
          {[0, 150, 300].map((delay) => (
            <span
              key={delay}
              className="size-2 rounded-full bg-primary/70 motion-safe:animate-bounce"
              style={{ animationDelay: `${delay}ms` }}
            />
          ))}
        </span>
        {LOADING_TEXT}
      </div>
    </div>
  );
}

export function MessageList({ entries, pending }: { entries: Entry[]; pending: boolean }) {
  return (
    <ol aria-label="Conversation" className="space-y-3">
      {entries.map((entry) => (
        <li key={entry.id}>
          {entry.role === "user" && <UserBubble text={entry.text} />}
          {entry.role === "assistant" && <AssistantBubble response={entry.response} />}
          {entry.role === "fallback" && <ReplyBubble message={fallbackMessage} badge="safety" />}
          {entry.role === "error" && <ErrorBubble state={entry.state} />}
        </li>
      ))}
      {pending && (
        <li>
          <LoadingBubble />
        </li>
      )}
    </ol>
  );
}
