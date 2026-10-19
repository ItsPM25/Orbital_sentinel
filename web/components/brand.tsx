import { cn } from "@/lib/utils";

/** The mark: a planet with one inclined orbit and the satellite on it. Line art in
 * currentColor so it follows the surrounding text colour. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className={cn("size-5", className)}>
      <circle cx="12" cy="12" r="5" stroke="currentColor" strokeWidth="1.6" />
      <ellipse cx="12" cy="12" rx="10.2" ry="4.2" transform="rotate(-24 12 12)" stroke="currentColor" strokeWidth="1.2" />
      <circle cx="20.6" cy="7.6" r="1.7" fill="currentColor" />
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-semibold tracking-tight", className)}>
      <BrandMark />
      Orbital Sentinel
    </span>
  );
}
