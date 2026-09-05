import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import type { KPI } from "../../types/contracts";

interface KpiCardProps {
  kpi: KPI;
}

export function KpiCard({ kpi }: KpiCardProps) {
  const hasDelta = kpi.delta != null;
  const isFlat = hasDelta && kpi.delta === 0;
  const isUp = hasDelta && (kpi.delta as number) > 0;

  return (
    <div className="kpi-item kpi-card" role="group" aria-label={kpi.label}>
      <span>{kpi.label}</span>
      <strong>
        {formatValue(kpi.value)}
        {kpi.unit ? <span className="kpi-card__unit"> {kpi.unit}</span> : null}
      </strong>
      {hasDelta && (
        <small
          className={`kpi-card__delta ${isFlat ? "kpi-card__delta--flat" : isUp ? "kpi-card__delta--up" : "kpi-card__delta--down"}`}
        >
          {isFlat ? <Minus aria-hidden="true" /> : isUp ? <ArrowUpRight aria-hidden="true" /> : <ArrowDownRight aria-hidden="true" />}
          {isUp ? "+" : ""}
          {kpi.delta}%
        </small>
      )}
    </div>
  );
}

function formatValue(value: number | string): string {
  if (typeof value !== "number") return String(value);
  if (Number.isInteger(value)) return value.toLocaleString();
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}
