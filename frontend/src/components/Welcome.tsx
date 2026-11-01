import { FEATURES, SCOPE_NOTICE, SUGGESTED_QUESTIONS, WELCOME } from "../content";
import { PrototypeBadge } from "./Badges";
import { ArrowRightIcon, BookIcon, CheckListIcon, InfoIcon, ShieldIcon } from "./Icons";

const FEATURE_ICONS = [BookIcon, ShieldIcon, CheckListIcon];

interface WelcomeProps {
  onAsk: (question: string) => void;
  disabled: boolean;
}

export function Welcome({ onAsk, disabled }: WelcomeProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <PrototypeBadge />
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          Hello! I'm <span className="text-primary">HealthChat AI</span>
        </h1>
        <p className="max-w-2xl text-base leading-relaxed text-muted">{WELCOME}</p>
      </div>

      <p
        role="note"
        className="flex items-start gap-2.5 rounded-xl border border-line bg-tint px-4 py-3 text-sm leading-relaxed"
      >
        <InfoIcon className="mt-0.5 size-5 shrink-0 text-primary" />
        <span>
          <strong className="font-semibold">Prototype:</strong> {SCOPE_NOTICE}
        </span>
      </p>

      <ul className="grid gap-3 sm:grid-cols-3" aria-label="What HealthChat AI aims to do">
        {FEATURES.map(({ title, text }, i) => {
          const Icon = FEATURE_ICONS[i];
          return (
            <li key={title} className="rounded-xl border border-line bg-white p-3 shadow-sm">
              <div className="flex items-center gap-2">
                <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-tint text-primary">
                  <Icon className="size-4" />
                </span>
                <p className="text-sm font-semibold">{title}</p>
              </div>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{text}</p>
            </li>
          );
        })}
      </ul>

      <section aria-labelledby="examples-heading" className="space-y-2">
        <h2 id="examples-heading" className="text-sm font-semibold">
          Try an example question
        </h2>
        <ul className="grid gap-2 sm:grid-cols-2">
          {SUGGESTED_QUESTIONS.map((question) => (
            <li key={question}>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onAsk(question)}
                className="group flex w-full items-center justify-between gap-3 rounded-xl border border-line bg-white px-3 py-2.5 text-left text-sm font-medium transition hover:border-primary hover:bg-tint focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-60"
              >
                {question}
                <ArrowRightIcon className="size-4 shrink-0 text-primary transition group-hover:translate-x-0.5" />
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
