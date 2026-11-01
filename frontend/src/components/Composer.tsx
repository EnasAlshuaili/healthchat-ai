import { useId, useState, type FormEvent, type KeyboardEvent } from "react";
import { charCount } from "../text";
import {
  DISCLAIMER,
  HARD_LIMIT_CHARS,
  INPUT_PLACEHOLDER,
  MAX_INPUT_CHARS,
  PRIVACY_HINT,
} from "../content";
import { InfoIcon, SendIcon } from "./Icons";

interface ComposerProps {
  onSend: (question: string) => void;
  pending: boolean;
}

/**
 * Message input. Over 1,000 characters shows a soft warning but still sends: the
 * server decides (API_CONTRACT "Frontend obligations"). Only the 20,000-character
 * scan limit blocks sending. No safety logic lives here.
 */
export function Composer({ onSend, pending }: ComposerProps) {
  const [draft, setDraft] = useState("");
  const inputId = useId();
  const hintId = useId();
  const count = charCount(draft);
  const overSoft = count > MAX_INPUT_CHARS;
  const overHard = count > HARD_LIMIT_CHARS;
  const canSend = !pending && draft.trim().length > 0 && !overHard;

  function submit() {
    if (!canSend) return;
    onSend(draft);
    setDraft("");
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <div className="border-t border-line bg-white/95 px-4 pt-2 pb-2 backdrop-blur sm:px-6">
      <form onSubmit={handleSubmit} className="mx-auto max-w-3xl">
        <label htmlFor={inputId} className="sr-only">
          Your question
        </label>
        <div className="flex items-end gap-2 rounded-2xl border border-line bg-white p-1 shadow-sm focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20">
          <textarea
            id={inputId}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={INPUT_PLACEHOLDER}
            rows={1}
            aria-describedby={hintId}
            aria-invalid={overHard || undefined}
            className="max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-sm leading-relaxed outline-none placeholder:text-slate-500 [field-sizing:content]"
          />
          <button
            type="submit"
            disabled={!canSend}
            aria-label="Send question"
            className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary text-white transition hover:bg-primary-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            <SendIcon className="size-5" />
          </button>
        </div>

        <div id={hintId} className="mt-1 flex flex-wrap items-start justify-between gap-x-4 gap-y-0.5 px-1 text-xs">
          <p aria-live="polite" className={overHard ? "font-medium text-red-700" : overSoft ? "font-medium text-amber-800" : "sr-only"}>
            {overHard
              ? `This message is too long to send (limit ${HARD_LIMIT_CHARS.toLocaleString("en")} characters).`
              : overSoft
                ? `Questions over ${MAX_INPUT_CHARS.toLocaleString("en")} characters usually can't be answered. You can still send it.`
                : ""}
          </p>
          <p className={`ml-auto tabular-nums ${overSoft ? "text-amber-800" : "text-muted"}`}>
            {count.toLocaleString("en")} / {MAX_INPUT_CHARS.toLocaleString("en")}
          </p>
        </div>

        <p className="mt-0.5 flex items-start gap-1.5 px-1 text-xs leading-snug text-muted">
          <InfoIcon className="size-3.5 shrink-0" />
          <span>
            {DISCLAIMER} {PRIVACY_HINT}
          </span>
        </p>
      </form>
    </div>
  );
}
