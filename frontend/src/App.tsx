import { useEffect, useRef, useState } from "react";
import { createHttpClient } from "./api/httpClient";
import { ChatError, type ChatClient } from "./api/types";
import { About } from "./components/About";
import { CloseIcon, MenuIcon } from "./components/Icons";
import { MessageList, type Entry } from "./components/Messages";
import { Composer } from "./components/Composer";
import { SafetyNotice } from "./components/SafetyNotice";
import { Brand, SidebarContent, type View } from "./components/Sidebar";
import { Welcome } from "./components/Welcome";
import type { ErrorState } from "./content";

// Phase C: the FastAPI backend (contract v0.3; D-19, D-21). No mock fallback.
const defaultClient = createHttpClient();

// Entry without its id; distributes over the union so each variant keeps its own fields.
type NewEntry = Entry extends infer E ? (E extends Entry ? Omit<E, "id"> : never) : never;

function errorState(error: unknown): ErrorState {
  if (!(error instanceof ChatError)) return "unexpected";
  if (error.kind === "network" || error.kind === "timeout") return "unreachable";
  if (error.kind === "http") return "unavailable";
  if (error.kind === "invalid_response") return "unreadable";
  return "unexpected";
}

export default function App({ client = defaultClient }: { client?: ChatClient }) {
  const [view, setView] = useState<View>("chat");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [pending, setPending] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const nextId = useRef(1);
  // The request in progress, if any. Checked synchronously so a double click or a
  // second Enter cannot send twice; replaced by "New chat" so a late reply is discarded.
  const inFlight = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Follow the conversation only; on the welcome screen keep the top (and safety notice) in view.
    if (entries.length > 0 || pending) endRef.current?.scrollIntoView?.({ block: "end" });
  }, [entries, pending]);

  useEffect(() => () => inFlight.current?.abort(), []);

  useEffect(() => {
    if (!menuOpen) return;
    drawerRef.current?.querySelector<HTMLElement>("button")?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeMenu();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  function closeMenu() {
    setMenuOpen(false);
    menuButtonRef.current?.focus();
  }

  function add(entry: NewEntry) {
    setEntries((current) => [...current, { ...entry, id: nextId.current++ }]);
  }

  async function ask(question: string) {
    if (inFlight.current) return;
    const request = new AbortController();
    inFlight.current = request;
    setView("chat");
    add({ role: "user", text: question });
    setPending(true);
    let reply: NewEntry;
    try {
      const outcome = await client.chat(question, request.signal);
      reply = outcome.type === "reply" ? { role: "assistant", response: outcome.response } : { role: "fallback" };
    } catch (error) {
      reply = { role: "error", state: errorState(error) };
    }
    if (inFlight.current !== request) return; // "New chat" was pressed meanwhile
    inFlight.current = null;
    add(reply);
    setPending(false);
  }

  function newChat() {
    inFlight.current?.abort();
    inFlight.current = null;
    setEntries([]);
    setPending(false);
    setView("chat");
    setMenuOpen(false);
  }

  function navigate(target: View) {
    setView(target);
    setMenuOpen(false);
  }

  const sidebarProps = { view, onNavigate: navigate, onNewChat: newChat };

  return (
    <div className="flex h-dvh bg-white text-ink">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:shadow"
      >
        Skip to main content
      </a>

      <aside className="hidden w-72 shrink-0 border-r border-line bg-surface lg:block" aria-label="Sidebar">
        <SidebarContent {...sidebarProps} />
      </aside>

      {menuOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="absolute inset-0 bg-ink/40" onClick={closeMenu} aria-hidden="true" />
          <div ref={drawerRef} className="relative h-full w-72 max-w-[85vw] bg-surface shadow-xl">
            <button
              type="button"
              onClick={closeMenu}
              aria-label="Close menu"
              className="absolute top-4 right-3 rounded-lg p-2 text-muted hover:bg-tint focus-visible:outline-2 focus-visible:outline-primary"
            >
              <CloseIcon className="size-5" />
            </button>
            <SidebarContent {...sidebarProps} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-line bg-white px-4 py-3 lg:hidden">
          <button
            ref={menuButtonRef}
            type="button"
            onClick={() => setMenuOpen(true)}
            aria-label="Open menu"
            aria-expanded={menuOpen}
            className="rounded-lg p-2 text-ink hover:bg-tint focus-visible:outline-2 focus-visible:outline-primary"
          >
            <MenuIcon className="size-5" />
          </button>
          <Brand />
        </header>

        <main id="main" tabIndex={-1} className="flex-1 overflow-y-auto focus:outline-none">
          <div className="mx-auto max-w-3xl space-y-6 px-4 py-6 sm:px-6 sm:py-10">
            {view === "about" ? (
              <About />
            ) : (
              <>
                <div className="lg:hidden">
                  <SafetyNotice compact />
                </div>
                {entries.length === 0 && !pending ? (
                  <Welcome onAsk={ask} disabled={pending} />
                ) : (
                  <>
                    <h1 className="sr-only">Conversation with QueryMate</h1>
                    <MessageList entries={entries} pending={pending} />
                  </>
                )}
                <div ref={endRef} />
              </>
            )}
          </div>
        </main>

        {view === "chat" && <Composer onSend={ask} pending={pending} />}
      </div>
    </div>
  );
}
