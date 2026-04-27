import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export type SweepAggregation = "mean" | "min" | "max" | "median" | "count";

interface SweepDimensionPickerProps {
  axes: { name: string; values: (string | number | boolean | null)[] }[];
  selected: [string, string | null];
  onChange: (next: [string, string | null]) => void;
  aggregations: Record<string, SweepAggregation>;
  onAggregationsChange: (next: Record<string, SweepAggregation>) => void;
}

const AGGREGATIONS: SweepAggregation[] = ["mean", "min", "max", "median", "count"];

export function SweepDimensionPicker({
  axes,
  selected,
  onChange,
  aggregations,
  onAggregationsChange,
}: SweepDimensionPickerProps) {
  if (axes.length < 3) return null;

  const [xAxis, yAxis] = selected;
  const unselected = axes.filter((axis) => axis.name !== xAxis && axis.name !== yAxis);

  const setX = (nextX: string) => {
    if (nextX === yAxis) {
      const fallback = axes.find((axis) => axis.name !== nextX)?.name ?? null;
      onChange([nextX, fallback]);
      return;
    }
    onChange([nextX, yAxis]);
  };

  const setY = (nextY: string | null) => {
    onChange([xAxis, nextY === xAxis ? null : nextY]);
  };

  return (
    <div className="rounded-lg border border-border bg-bg-1 p-3">
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="X axis">
          <AxisSelect axes={axes} value={xAxis} onChange={setX} />
        </Field>
        <Field label="Y axis">
          <AxisSelect axes={axes} value={yAxis ?? ""} onChange={(value) => setY(value || null)} />
        </Field>
      </div>
      {unselected.length > 0 ? (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-muted-2">
            Aggregate over
          </span>
          {unselected.map((axis) => (
            <label
              key={axis.name}
              className="inline-flex items-center gap-1.5 rounded border border-border bg-bg-2 px-2 py-1 text-[11px] text-muted"
            >
              <span className="font-mono text-text">{axis.name}</span>
              <select
                value={aggregations[axis.name] ?? defaultAggregation(axis)}
                onChange={(event) =>
                  onAggregationsChange({
                    ...aggregations,
                    [axis.name]: event.target.value as SweepAggregation,
                  })
                }
                className="rounded border border-border bg-bg-inset px-1 py-0.5 text-[11px] text-text outline-none focus:border-accent"
              >
                {AGGREGATIONS.map((agg) => (
                  <option key={agg} value={agg}>
                    {agg}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 text-[11px] font-medium uppercase tracking-[0.08em] text-muted-2">
      <div>{label}</div>
      {children}
    </div>
  );
}

function AxisSelect({
  axes,
  value,
  onChange,
}: {
  axes: { name: string }[];
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className={cn(
        "h-8 rounded border border-border bg-bg-inset px-2 text-[12px] normal-case tracking-normal text-text",
        "outline-none transition-colors focus:border-accent",
      )}
    >
      <option value="">none</option>
      {axes.map((axis) => (
        <option key={axis.name} value={axis.name}>
          {axis.name}
        </option>
      ))}
    </select>
  );
}

function defaultAggregation(axis: { values: unknown[] }): SweepAggregation {
  return axis.values.every((value) => typeof value === "number") ? "mean" : "count";
}
