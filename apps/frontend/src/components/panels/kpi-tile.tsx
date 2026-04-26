import { KPI } from "@/components/ui/kpi";
import { formatCost, formatDurationMs, formatNumber, formatTokens } from "@/lib/utils";

interface KpiTileProps {
  label: string;
  value: unknown;
  format: "int" | "duration" | "cost" | "tokens" | "number" | "string";
  sub?: string | undefined;
}

export function KpiTile({ label, value, format, sub }: KpiTileProps) {
  const display = formatValue(value, format);
  return <KPI label={label} value={display} sub={sub ?? null} />;
}

function formatValue(value: unknown, format: KpiTileProps["format"]): string {
  if (value == null) return "—";
  switch (format) {
    case "int":
      return typeof value === "number" ? Math.round(value).toString() : String(value);
    case "duration":
      return typeof value === "number" ? formatDurationMs(value) : "—";
    case "cost":
      return typeof value === "number" ? formatCost(value) : "—";
    case "tokens":
      return typeof value === "number" ? formatTokens(value) : "—";
    case "number":
      return typeof value === "number" ? formatNumber(value) : "—";
    default:
      return String(value);
  }
}
