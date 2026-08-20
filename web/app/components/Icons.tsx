/**
 * Inline SVG icons.
 *
 * Kept local rather than pulled from an icon package: there are twelve of them,
 * they all share one stroke treatment, and a dependency for this would be more
 * bytes than the icons.
 */
interface IconProps {
  size?: number;
  className?: string;
}

const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
});

export const IconArchive = ({ size = 16, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M3 7h18v13a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7Z" />
    <path d="M2 3h20v4H2z" />
    <path d="M10 12h4" />
  </svg>
);

export const IconFolder = ({ size = 16, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M3 7a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7Z" />
  </svg>
);

export const IconGit = ({ size = 16, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <circle cx="12" cy="5" r="2.4" />
    <circle cx="6" cy="19" r="2.4" />
    <circle cx="18" cy="19" r="2.4" />
    <path d="M12 7.4v4.2M12 11.6a6 6 0 0 1-6 5M12 11.6a6 6 0 0 0 6 5" />
  </svg>
);

export const IconUpload = ({ size = 22, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M12 16V4M12 4 7.5 8.5M12 4l4.5 4.5" />
    <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
  </svg>
);

export const IconPlay = ({ size = 15, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M6.5 4.5 18 12 6.5 19.5V4.5Z" fill="currentColor" strokeWidth={1.4} />
  </svg>
);

export const IconDownload = ({ size = 15, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M12 4v11M12 15l-4-4M12 15l4-4" />
    <path d="M5 19h14" />
  </svg>
);

export const IconCopy = ({ size = 15, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M5 15H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v1" />
  </svg>
);

export const IconCheck = ({ size = 15, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="m4.5 12.5 5 5 10-11" />
  </svg>
);

export const IconAlert = ({ size = 17, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7.5v5.5M12 16.3v.2" />
  </svg>
);

export const IconClose = ({ size = 14, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="m6 6 12 12M18 6 6 18" />
  </svg>
);

export const IconSliders = ({ size = 15, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M4 8h10M18 8h2M4 16h4M12 16h8" />
    <circle cx="16" cy="8" r="2" />
    <circle cx="10" cy="16" r="2" />
  </svg>
);

export const IconTree = ({ size = 15, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M6 4v13a1 1 0 0 0 1 1h3M6 10h4" />
    <rect x="13" y="7" width="7" height="5" rx="1" />
    <rect x="13" y="15" width="7" height="5" rx="1" />
  </svg>
);

export const IconDoc = ({ size = 15, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M14 3H7a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7l-4-4Z" />
    <path d="M14 3v4h4M9 13h6M9 17h4" />
  </svg>
);
