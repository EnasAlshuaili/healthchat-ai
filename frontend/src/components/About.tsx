import { DESCRIPTION, DISCLAIMER, PROTOTYPE_NOTICE, TAGLINE } from "../content";
import { InfoIcon } from "./Icons";

const STEPS = [
  ["You ask a question", "Type a general health question. Avoid personal details."],
  [
    "Safety checks run first",
    "Possible emergencies, dosage and diagnosis requests, and out-of-scope questions get safety guidance instead of an answer.",
  ],
  [
    "Owner-reviewed content is matched",
    "If nothing fits well, you get a safe fallback instead of a guess.",
  ],
] as const;

export function About() {
  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">About HealthChat AI</h1>
        <p className="text-base leading-relaxed text-muted">
          {DESCRIPTION}. {TAGLINE}
        </p>
        <p role="note" className="flex items-start gap-2.5 rounded-xl border border-line bg-tint px-4 py-3 text-sm leading-relaxed">
          <InfoIcon className="mt-0.5 size-5 shrink-0 text-primary" />
          {PROTOTYPE_NOTICE}
        </p>
      </div>

      <section aria-labelledby="how-heading" className="space-y-2">
        <h2 id="how-heading" className="text-lg font-semibold">
          How it is designed to work
        </h2>
        <p className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          <strong className="font-semibold">Limited to one topic.</strong> Step 2 runs as an automated,
          keyword-based prototype check, not clinical triage. Step 3 covers hydration only, using educational
          content reviewed by the project owner, not clinically reviewed. Other questions get a safe fallback.
        </p>
        <ol className="grid gap-3 sm:grid-cols-3">
          {STEPS.map(([title, text], i) => (
            <li key={title} className="rounded-xl border border-line bg-white p-3 shadow-sm">
              <div className="flex items-center gap-2">
                <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-tint text-sm font-bold text-primary">
                  {i + 1}
                </span>
                <p className="text-sm font-semibold">{title}</p>
              </div>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="privacy-heading" className="space-y-2">
        <h2 id="privacy-heading" className="text-lg font-semibold">
          Privacy
        </h2>
        <ul className="list-disc space-y-1 pl-5 text-sm leading-relaxed">
          <li>Chats stay in this browser tab and are never saved.</li>
          <li>No questions are sent to external AI services.</li>
          <li>Questions go only to the local HealthChat AI service on this computer, which does not store them.</li>
        </ul>
      </section>

      <section aria-labelledby="important-heading" className="space-y-2">
        <h2 id="important-heading" className="text-lg font-semibold">
          Important
        </h2>
        <p className="text-sm leading-relaxed">{DISCLAIMER}</p>
      </section>
    </div>
  );
}
