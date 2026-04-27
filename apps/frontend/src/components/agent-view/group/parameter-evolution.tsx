import { ParameterDiffPanel } from "@/components/agent-view/group/parameter-diff-panel";
import { EmptyState, HashTag, PanelCard } from "@/components/ui";
import { hashColor, hashColorDim } from "@/lib/hash-color";
import { truncateMiddle } from "@/lib/utils";
import { useMemo, useState } from "react";

export type ParameterPoint = {
  runId: string;
  startedAt: number;
  value: unknown;
  hash: string;
};

export type ParameterSeries = {
  path: string;
  points: ParameterPoint[];
};

export function ParameterEvolution({ series }: { series: ParameterSeries[] }) {
  if (series.length === 0) {
    return (
      <EmptyState
        title="no trainable parameter series"
        description="this group has no captured parameter values yet"
      />
    );
  }

  return (
    <div className="space-y-3">
      {series.map((item) => (
        <ParameterEvolutionPanel key={item.path} series={item} />
      ))}
    </div>
  );
}

function ParameterEvolutionPanel({ series }: { series: ParameterSeries }) {
  const [selectedHash, setSelectedHash] = useState<string | null>(null);
  const lanes = useMemo(() => laneValues(series.points), [series.points]);
  const selectedLane = selectedHash ? lanes.find((lane) => lane.hash === selectedHash) : null;
  const selectedIndex = selectedHash
    ? series.points.findIndex((point) => point.hash === selectedHash)
    : -1;
  const previousPoint = selectedIndex > 0 ? series.points[selectedIndex - 1] : null;
  const currentPoint = selectedIndex >= 0 ? series.points[selectedIndex] : null;

  return (
    <PanelCard
      title={series.path}
      eyebrow={`${lanes.length} distinct value${lanes.length === 1 ? "" : "s"} seen`}
      bodyMinHeight={180}
    >
      <div className="space-y-2">
        <div className="overflow-auto">
          <div
            className="grid min-w-[520px] gap-1"
            style={{
              gridTemplateColumns: `160px repeat(${Math.max(series.points.length, 1)}, minmax(28px, 1fr))`,
            }}
          >
            <span />
            {series.points.map((point, index) => (
              <div
                key={point.runId}
                className="truncate text-center font-mono text-[10px] text-muted-2"
              >
                {index + 1}
              </div>
            ))}
            {lanes.map((lane) => (
              <Row
                key={lane.hash}
                lane={lane}
                points={series.points}
                selected={selectedHash === lane.hash}
                onSelect={() => setSelectedHash(lane.hash)}
              />
            ))}
          </div>
        </div>
        {selectedLane && currentPoint ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-[12px] text-muted">
              <HashTag hash={selectedLane.hash} mono size="sm" />
              <span className="font-mono">{truncateMiddle(currentPoint.runId, 18)}</span>
            </div>
            <ParameterDiffPanel
              path={series.path}
              previous={previousPoint?.value}
              current={currentPoint.value}
            />
          </div>
        ) : null}
      </div>
    </PanelCard>
  );
}

function Row({
  lane,
  points,
  selected,
  onSelect,
}: {
  lane: { hash: string; label: string };
  points: ParameterPoint[];
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <>
      <button
        type="button"
        onClick={onSelect}
        className="min-w-0 truncate rounded px-2 py-1 text-left font-mono text-[11px] text-text hover:bg-bg-2"
        title={lane.label}
      >
        {truncateMiddle(lane.label, 26)}
      </button>
      {points.map((point) => {
        const active = point.hash === lane.hash;
        return (
          <button
            key={`${lane.hash}-${point.runId}`}
            type="button"
            onClick={onSelect}
            className="flex h-7 items-center justify-center rounded border border-border transition-colors hover:border-border-strong"
            style={{
              background: active ? hashColorDim(lane.hash, selected ? 0.42 : 0.22) : "transparent",
            }}
            aria-label={`${lane.label} at ${point.runId}`}
          >
            {active ? (
              <span className="h-2 w-2 rounded-full" style={{ background: hashColor(lane.hash) }} />
            ) : null}
          </button>
        );
      })}
    </>
  );
}

function laneValues(points: ParameterPoint[]): Array<{ hash: string; label: string }> {
  const lanes = new Map<string, string>();
  for (const point of points) {
    if (!lanes.has(point.hash)) lanes.set(point.hash, stringifyValue(point.value));
  }
  return [...lanes.entries()].map(([hash, label]) => ({ hash, label }));
}

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}
