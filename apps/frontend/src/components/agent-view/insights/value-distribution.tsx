import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { formatNumber } from "@/lib/utils";
import { useUIStore } from "@/stores/ui";

export interface ValueDistributionProps {
  label: string;
  values: unknown[];
  agentPath?: string | null;
  side?: "in" | "out";
  className?: string;
}

interface CategoryRow {
  label: string;
  count: number;
}

export function ValueDistribution({ label, values, agentPath, side = "in", className }: ValueDistributionProps) {
  const openDrawer = useUIStore((s) => s.openDrawer);
  if (values.length === 0) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>{label}</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <EmptyState title="no values yet" />
        </CardContent>
      </Card>
    );
  }

  const numeric = values.every((value) => typeof value === "number" && Number.isFinite(value));
  if (numeric) {
    const nums = values as number[];
    const min = Math.min(...nums);
    const max = Math.max(...nums);
    const avg = nums.reduce((sum, n) => sum + n, 0) / nums.length;
    const points = sparkPoints(nums, 180, 38);
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>{label}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <svg width="100%" height={38} viewBox="0 0 180 38" className="block">
            <polyline
              fill="none"
              stroke="var(--color-accent)"
              strokeWidth={1.8}
              points={points.map((point) => `${point.x},${point.y}`).join(" ")}
            />
          </svg>
          <div className="text-[0.68rem] text-muted">
            min {formatNumber(min)} · avg {formatNumber(avg)} · max {formatNumber(max)}
          </div>
        </CardContent>
      </Card>
    );
  }

  const stringValues = values.map(toCategoryLabel);
  const counts = new Map<string, number>();
  for (const item of stringValues) {
    counts.set(item, (counts.get(item) ?? 0) + 1);
  }
  const rows: CategoryRow[] = [...counts.entries()]
    .map(([name, count]) => ({ label: name, count }))
    .sort((a, b) => b.count - a.count);
  const highCardinality = rows.length > 12;
  const topRows = rows.slice(0, 5);
  const maxCount = Math.max(...topRows.map((row) => row.count), 1);

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>{label}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {highCardinality ? (
          <button
            type="button"
            className="text-[0.72rem] text-accent hover:underline"
            onClick={() => {
              if (!agentPath) return;
              openDrawer("values", { agentPath, attr: label, side });
            }}
          >
            see all values ({rows.length} unique)
          </button>
        ) : null}
        {topRows.map((row) => (
          <div key={row.label} className="space-y-1">
            <div className="flex items-center justify-between text-[0.68rem] text-muted">
              <span className="truncate pr-2">{row.label}</span>
              <span>{row.count}</span>
            </div>
            <div className="h-1 rounded bg-bg-3">
              <div
                className="h-1 rounded bg-accent"
                style={{ width: `${Math.max(6, (row.count / maxCount) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function sparkPoints(values: number[], width: number, height: number): Array<{ x: number; y: number }> {
  if (values.length === 1) {
    return [{ x: 0, y: height / 2 }];
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1e-9, max - min);
  return values.map((value, index) => ({
    x: (index / (values.length - 1)) * width,
    y: height - ((value - min) / span) * height,
  }));
}

function toCategoryLabel(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  return JSON.stringify(value);
}
