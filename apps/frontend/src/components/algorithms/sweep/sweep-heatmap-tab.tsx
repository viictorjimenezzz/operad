import { ParallelCoordinates } from "@/components/algorithms/sweep/parallel-coordinates";
import {
  type SweepAggregation,
  SweepDimensionPicker,
} from "@/components/algorithms/sweep/sweep-dimension-picker";
import { SweepHeatmap } from "@/components/charts/sweep-heatmap";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useUrlState } from "@/hooks/use-url-state";
import { RunSummary as RunSummarySchema, SweepSnapshot } from "@/lib/types";
import { useEffect, useMemo, useState } from "react";
import { z } from "zod";

const ChildRunSummary = RunSummarySchema.passthrough().extend({
  hash_content: z.string().nullable().optional(),
});

interface SweepHeatmapTabProps {
  data: unknown;
  dataChildren?: unknown;
}

export function SweepHeatmapTab({ data, dataChildren }: SweepHeatmapTabProps) {
  const parsed = SweepSnapshot.safeParse(data);
  const [dimParam, setDimParam] = useUrlState("dim");
  const [aggParam, setAggParam] = useUrlState("agg");
  const [parallel, setParallel] = useState(false);

  const snap = parsed.success ? parsed.data : null;
  const defaults = useMemo(
    () => (snap ? defaultSelection(snap.axes) : (["", null] as [string, string | null])),
    [snap],
  );
  const selected = parseDim(dimParam, snap?.axes ?? []) ?? defaults;
  const aggregations = parseAgg(aggParam, snap?.axes ?? []);
  const cellHrefs = useMemo(() => childHrefsByCell(dataChildren), [dataChildren]);

  useEffect(() => {
    if (!snap || snap.axes.length < 3) return;
    if (dimParam != null) return;
    setDimParam(selected[1] ? `${selected[0]},${selected[1]}` : selected[0]);
  }, [dimParam, selected, setDimParam, snap]);

  if (!snap) {
    return <EmptyState title="no sweep data" description="waiting for sweep events" />;
  }

  if (snap.axes.length === 0) {
    return (
      <EmptyState title="no sweep axes" description="this sweep did not emit parameter axes" />
    );
  }

  const setSelected = (next: [string, string | null]) => {
    setDimParam(next[1] ? `${next[0]},${next[1]}` : next[0]);
  };

  const setAggregations = (next: Record<string, SweepAggregation>) => {
    const raw = Object.entries(next)
      .filter(([, value]) => value)
      .map(([axis, value]) => `${axis}:${value}`)
      .join(",");
    setAggParam(raw || null);
  };

  return (
    <div className="flex flex-col gap-3">
      {snap.axes.length >= 3 ? (
        <div className="flex flex-col gap-2">
          <SweepDimensionPicker
            axes={snap.axes.map((axis) => ({
              name: axis.name,
              values: axis.values.map((value) =>
                value == null || ["string", "number", "boolean"].includes(typeof value)
                  ? (value as string | number | boolean | null)
                  : String(value),
              ),
            }))}
            selected={selected}
            onChange={setSelected}
            aggregations={aggregations}
            onAggregationsChange={setAggregations}
          />
          <div className="flex justify-end">
            <Button
              size="sm"
              variant={parallel ? "primary" : "default"}
              onClick={() => setParallel((v) => !v)}
            >
              parallel coordinates
            </Button>
          </div>
        </div>
      ) : null}
      {parallel && snap.axes.length > 2 ? (
        <ParallelCoordinates data={snap} />
      ) : (
        <SweepHeatmap
          data={snap}
          xAxis={selected[0]}
          yAxis={selected[1]}
          aggregations={aggregations}
          cellHrefs={cellHrefs}
        />
      )}
    </div>
  );
}

function childHrefsByCell(data: unknown): Record<number, string> {
  const parsed = z.array(ChildRunSummary).safeParse(data);
  if (!parsed.success) return {};
  const out: Record<number, string> = {};
  [...parsed.data]
    .sort((a, b) => (a.started_at ?? 0) - (b.started_at ?? 0))
    .forEach((child, index) => {
      const identity = child.hash_content ?? child.root_agent_path ?? child.run_id;
      out[index] =
        `/agents/${encodeURIComponent(identity)}/runs/${encodeURIComponent(child.run_id)}`;
    });
  return out;
}

function defaultSelection(axes: { name: string; values: unknown[] }[]): [string, string | null] {
  if (axes.length === 0) return ["", null];
  if (axes.length === 1) return [axes[0]?.name ?? "", null];
  const numeric = axes.filter((axis) => axis.values.some((value) => typeof value === "number"));
  const first = numeric[0]?.name ?? axes[0]?.name ?? "";
  const second =
    numeric.find((axis) => axis.name !== first)?.name ??
    axes.find((axis) => axis.name !== first)?.name ??
    null;
  return [first, second];
}

function parseDim(
  raw: string | null,
  axes: { name: string; values: unknown[] }[],
): [string, string | null] | null {
  if (!raw) return null;
  const names = new Set(axes.map((axis) => axis.name));
  const [x, y] = raw.split(",");
  if (!x || !names.has(x)) return null;
  return [x, y && names.has(y) && y !== x ? y : null];
}

function parseAgg(
  raw: string | null,
  axes: { name: string; values: unknown[] }[],
): Record<string, SweepAggregation> {
  const names = new Set(axes.map((axis) => axis.name));
  const out: Record<string, SweepAggregation> = {};
  for (const axis of axes) {
    out[axis.name] = axis.values.every((value) => typeof value === "number") ? "mean" : "count";
  }
  if (!raw) return out;
  for (const part of raw.split(",")) {
    const [axis, fn] = part.split(":");
    if (!axis || !names.has(axis)) continue;
    if (fn === "mean" || fn === "min" || fn === "max" || fn === "median" || fn === "count") {
      out[axis] = fn;
    }
  }
  return out;
}
