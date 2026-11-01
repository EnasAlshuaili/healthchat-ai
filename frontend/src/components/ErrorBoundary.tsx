import { Component, type ReactNode } from "react";
import { DISCLAIMER, ERROR_HEADINGS, SAFETY_NOTICE, SERVICE_ERROR } from "../content";
import { AlertIcon } from "./Icons";

/**
 * Last line of defence for unexpected client-side errors: if rendering fails, show the
 * generic service error, the safety notice, and the disclaimer instead of a blank page.
 * The error itself is never shown or logged anywhere.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="mx-auto max-w-3xl space-y-4 px-4 py-10 text-ink">
        <div role="alert" className="rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-900">
          <h1 className="flex items-center gap-2 font-semibold">
            <AlertIcon className="size-4 text-red-700" />
            {ERROR_HEADINGS.unexpected}
          </h1>
          <p className="mt-1.5 leading-relaxed">{SERVICE_ERROR}</p>
        </div>
        <p className="text-sm leading-relaxed">
          <strong className="font-semibold">Safety notice:</strong> {SAFETY_NOTICE}
        </p>
        <p className="text-sm leading-relaxed text-muted">{DISCLAIMER}</p>
      </main>
    );
  }
}
