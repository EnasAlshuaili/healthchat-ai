import { SAFETY_NOTICE } from "../content";
import { AlertIcon } from "./Icons";

/** Safety notice. Uses an icon and a text heading, so it never relies on colour alone. */
export function SafetyNotice({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return (
      <p className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900">
        <AlertIcon className="mt-0.5 size-4 shrink-0 text-red-700" />
        <span>
          <strong className="font-semibold">Safety notice:</strong> {SAFETY_NOTICE}
        </span>
      </p>
    );
  }
  return (
    <section
      aria-labelledby="safety-notice-heading"
      className="rounded-xl border border-red-200 bg-red-50 p-3 text-red-900"
    >
      <h2 id="safety-notice-heading" className="flex items-center gap-2 text-sm font-semibold">
        <AlertIcon className="size-4 text-red-700" />
        Safety notice
      </h2>
      <p className="mt-1.5 text-sm leading-relaxed">{SAFETY_NOTICE}</p>
    </section>
  );
}
