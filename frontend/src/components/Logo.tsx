export function LogoMark({ className = "size-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="#1D4ED8" />
      <path
        d="M9 22.5 15.2 8.8a.9.9 0 0 1 1.6 0L23 22.5"
        fill="none"
        stroke="#fff"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M11.8 17.6h8.4" stroke="#F97316" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  );
}

export function Logo() {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark />
      <span className="text-[15px] font-semibold tracking-tight text-fg">
        ASITECH <span className="text-primary">OPS</span>
      </span>
    </span>
  );
}
