// Small inline icons (decorative; always aria-hidden). No icon library dependency.
import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function Svg({ children, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  );
}

export const PlusIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 5v14M5 12h14" />
  </Svg>
);

export const SendIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 12 20 4l-6 16-3-7-7-1Z" />
  </Svg>
);

export const ArrowRightIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </Svg>
);

export const ChatIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M5 5h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H10l-5 4v-4H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" />
  </Svg>
);

export const InfoIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5M12 8h.01" />
  </Svg>
);

export const AlertIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 3 2 20h20L12 3Z" />
    <path d="M12 10v4M12 17h.01" />
  </Svg>
);

export const ShieldIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6l-7-3Z" />
    <path d="m9 12 2 2 4-4" />
  </Svg>
);

export const BookIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5Z" />
    <path d="M4 19a2 2 0 0 1 2-2h13" />
  </Svg>
);

export const CheckListIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="m4 7 2 2 3-3M4 15l2 2 3-3M13 8h7M13 16h7" />
  </Svg>
);

export const FlaskIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.7 3h10.6A2 2 0 0 0 19 18l-5-9V3" />
    <path d="M7.5 14h9" />
  </Svg>
);

export const MenuIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </Svg>
);

export const CloseIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </Svg>
);

export const UserIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21a8 8 0 0 1 16 0" />
  </Svg>
);

export const BotIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="4" y="7" width="16" height="12" rx="3" />
    <path d="M12 3v4M9 12h.01M15 12h.01M9 16h6" />
  </Svg>
);

export const SchoolIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="m2 9 10-5 10 5-10 5L2 9Z" />
    <path d="M6 11v5c3 2 9 2 12 0v-5" />
  </Svg>
);

/** HealthChat AI mark: same shape as assets/querymate_icon.svg. */
export const LogoMark = (p: IconProps) => (
  <svg viewBox="0 0 40 40" aria-hidden="true" focusable="false" {...p}>
    <rect x="4" y="4" width="32" height="28" rx="8" fill="#2563EB" />
    <path d="M12 32 L12 38 L19 32 Z" fill="#2563EB" />
    <rect x="18" y="10" width="4" height="16" rx="1.5" fill="#FFFFFF" />
    <rect x="12" y="16" width="16" height="4" rx="1.5" fill="#FFFFFF" />
  </svg>
);
