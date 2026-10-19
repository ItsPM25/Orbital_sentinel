import { BAND_LABEL, bandVar, riskBand, type RiskBand } from "@/lib/risk";
import { cn } from "@/lib/utils";

/** A square swatch in the band's colour. Squares, not glowing dots. */
export function BandSwatch({ band, className }: { band: RiskBand; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn("inline-block size-2.5 shrink-0 rounded-[2px]", className)}
      style={{ background: bandVar(band) }}
    />
  );
}

/** Risk level 1-10 as a ten-segment meter, the number and the band name. */
export function RiskMeter({ level, showLabel = true, className }: { level: number | null; showLabel?: boolean; className?: string }) {
  const band = riskBand(level);
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span aria-hidden="true" className="flex gap-[2px]">
        {Array.from({ length: 10 }, (_, i) => (
          <span
            key={i}
            className="h-3 w-[3px] rounded-[1px]"
            style={{ background: level != null && i < level ? bandVar(band) : "var(--border)" }}
          />
        ))}
      </span>
      <span className="riskValue num font-medium">{level ?? "–"}</span>
      {showLabel && (
        <span className="riskLabel text-[13px]" style={{ color: bandVar(band) }}>
          {BAND_LABEL[band]}
        </span>
      )}
    </span>
  );
}

/** A severity string from the API (LOW/MEDIUM/HIGH/CRITICAL) shown as swatch + name. */
export function SeverityLabel({ severity }: { severity: string | null }) {
  if (!severity) return <span className="text-muted-foreground">–</span>;
  const band = severity.toLowerCase() as RiskBand;
  return (
    <span className="inline-flex items-center gap-1.5">
      <BandSwatch band={band in BAND_LABEL ? band : "none"} />
      {BAND_LABEL[band] ?? severity}
    </span>
  );
}

const STATUS_STYLE: Record<string, string> = {
  AlertRaised: "border-[color:var(--risk-critical)] text-[color:var(--risk-critical)]",
  Acknowledged: "border-border text-foreground",
  Resolved: "border-border text-muted-foreground",
};

/** Alert status, shown with the exact state names from the Exp 5 state diagram. */
export function StatusTag({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "num inline-flex h-5 items-center rounded-[3px] border px-1.5 text-[12px] leading-none",
        STATUS_STYLE[status] ?? "border-border text-muted-foreground",
      )}
    >
      {status}
    </span>
  );
}
