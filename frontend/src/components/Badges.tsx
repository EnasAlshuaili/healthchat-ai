import { CURATED_LABEL, MOCK_LABEL, SAFETY_LABEL } from "../content";
import { FlaskIcon, SchoolIcon, ShieldIcon } from "./Icons";

export function MockBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
      <FlaskIcon className="size-3.5" />
      {MOCK_LABEL}
    </span>
  );
}

/** For fixed safety templates (content_source "safety_template"). Never implies clinical review. */
export function SafetyBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-0.5 text-xs font-medium text-slate-700 ring-1 ring-slate-300">
      <ShieldIcon className="size-3.5" />
      {SAFETY_LABEL}
    </span>
  );
}

/** For curated answers (content_source "curated_owner_reviewed"). Owner review only, never clinical. */
export function CuratedBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-tint px-2.5 py-0.5 text-xs font-medium text-primary-strong ring-1 ring-line">
      <SchoolIcon className="size-3.5" />
      {CURATED_LABEL}
    </span>
  );
}

export function PrototypeBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-tint px-3 py-1 text-xs font-medium text-primary-strong ring-1 ring-line">
      <SchoolIcon className="size-3.5" />
      Educational prototype
    </span>
  );
}
