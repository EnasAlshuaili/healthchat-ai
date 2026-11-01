import { APP_NAME, CHATS_NOT_SAVED } from "../content";
import { PrototypeBadge } from "./Badges";
import { ChatIcon, InfoIcon, LogoMark, PlusIcon } from "./Icons";
import { SafetyNotice } from "./SafetyNotice";

export type View = "chat" | "about";

interface SidebarProps {
  view: View;
  onNavigate: (view: View) => void;
  onNewChat: () => void;
}

const NAV: { view: View; label: string; Icon: typeof ChatIcon }[] = [
  { view: "chat", label: "Chat", Icon: ChatIcon },
  { view: "about", label: "About", Icon: InfoIcon },
];

export function Brand() {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark className="size-9" />
      <span className="text-xl font-bold tracking-tight text-primary-strong">{APP_NAME}</span>
    </span>
  );
}

export function SidebarContent({ view, onNavigate, onNewChat }: SidebarProps) {
  return (
    <div className="flex h-full flex-col gap-6 p-5">
      <Brand />

      <div>
        <button
          type="button"
          onClick={onNewChat}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-primary-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          <PlusIcon className="size-4" />
          New chat
        </button>
        <p className="mt-2 text-xs leading-relaxed text-muted">{CHATS_NOT_SAVED}</p>
      </div>

      <nav aria-label="Main">
        <ul className="space-y-1">
          {NAV.map(({ view: target, label, Icon }) => {
            const current = view === target;
            return (
              <li key={target}>
                <button
                  type="button"
                  onClick={() => onNavigate(target)}
                  aria-current={current ? "page" : undefined}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
                    current ? "bg-tint-strong text-primary-strong" : "text-ink hover:bg-tint"
                  }`}
                >
                  <Icon className="size-4" />
                  {label}
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="mt-auto space-y-4">
        <SafetyNotice />
        <PrototypeBadge />
      </div>
    </div>
  );
}
