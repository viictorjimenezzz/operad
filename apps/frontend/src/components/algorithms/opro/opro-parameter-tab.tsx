import {
  type OPROStep,
  buildOPROSteps,
  shortText,
} from "@/components/algorithms/opro/opro-history-tab";
import { MultiPromptDiff } from "@/components/charts/multi-prompt-diff";
import { EmptyState, HashTag, PanelCard } from "@/components/ui";
import { hashColor, hashColorDim } from "@/lib/hash-color";
import { useMemo, useState } from "react";

export function OPROParameterTab({
  dataIterations,
  dataEvents,
  dataChildren,
}: {
  dataIterations?: unknown;
  dataEvents?: unknown;
  dataChildren?: unknown;
}) {
  const series = useMemo(
    () => buildParameterSeries(buildOPROSteps(dataIterations, dataEvents, dataChildren)),
    [dataIterations, dataEvents, dataChildren],
  );

  if (series.length === 0) {
    return (
      <EmptyState
        title="no accepted parameter values"
        description="the parameter lane appears after OPRO accepts a candidate rewrite"
      />
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <div className="space-y-3">
        {series.map((item) => (
          <ParameterPanel key={item.path} series={item} />
        ))}
      </div>
    </div>
  );
}

interface ParameterPoint {
  stepIndex: number;
  value: string;
  hash: string;
  score: number | null;
}

interface ParameterSeries {
  path: string;
  points: ParameterPoint[];
}

function ParameterPanel({ series }: { series: ParameterSeries }) {
  const lanes = useMemo(() => laneValues(series.points), [series.points]);
  const [selectedIndex, setSelectedIndex] = useState(() => Math.max(0, series.points.length - 1));
  const current = series.points[selectedIndex] ?? null;
  const previous = selectedIndex > 0 ? series.points[selectedIndex - 1] : null;

  return (
    <PanelCard
      title={series.path}
      eyebrow={`${lanes.length} distinct value${lanes.length === 1 ? "" : "s"} accepted`}
      bodyMinHeight={200}
    >
      <div className="space-y-3">
        <div className="overflow-auto">
          <div
            className="grid min-w-[560px] gap-1"
            style={{
              gridTemplateColumns: `180px repeat(${Math.max(series.points.length, 1)}, minmax(34px, 1fr))`,
            }}
          >
            <span />
            {series.points.map((point) => (
              <div
                key={`head-${point.stepIndex}`}
                className="truncate text-center font-mono text-[10px] text-muted-2"
              >
                {point.stepIndex}
              </div>
            ))}
            {lanes.map((lane) => (
              <LaneRow
                key={lane.hash}
                lane={lane}
                points={series.points}
                selectedIndex={selectedIndex}
                onSelect={setSelectedIndex}
              />
            ))}
          </div>
        </div>
        {current ? (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted">
              <HashTag hash={current.hash} mono size="sm" />
              <span>step {current.stepIndex}</span>
              <span>score {current.score != null ? current.score.toFixed(3) : "-"}</span>
              <span className="min-w-0 truncate">{shortText(current.value, 100)}</span>
            </div>
            {previous ? (
              <MultiPromptDiff
                prompts={[
                  {
                    runId: `${series.path}:${previous.stepIndex}`,
                    label: `step ${previous.stepIndex}`,
                    text: previous.value,
                  },
                  {
                    runId: `${series.path}:${current.stepIndex}`,
                    label: `step ${current.stepIndex}`,
                    text: current.value,
                  },
                ]}
              />
            ) : (
              <EmptyState
                title="no previous accepted value"
                description="select a later value to compare it against the prior accepted rewrite"
                className="min-h-32"
              />
            )}
          </div>
        ) : null}
      </div>
    </PanelCard>
  );
}

function LaneRow({
  lane,
  points,
  selectedIndex,
  onSelect,
}: {
  lane: { hash: string; label: string };
  points: ParameterPoint[];
  selectedIndex: number;
  onSelect: (index: number) => void;
}) {
  return (
    <>
      <div
        className="min-w-0 truncate rounded px-2 py-1 font-mono text-[11px] text-text"
        title={lane.label}
      >
        {shortText(lane.label, 32)}
      </div>
      {points.map((point, index) => {
        const active = point.hash === lane.hash;
        const selected = selectedIndex === index;
        return (
          <button
            key={`${lane.hash}-${point.stepIndex}`}
            type="button"
            disabled={!active}
            onClick={() => onSelect(index)}
            className="flex h-7 items-center justify-center rounded border border-border transition-colors enabled:hover:border-border-strong disabled:cursor-default"
            style={{
              background: active ? hashColorDim(lane.hash, selected ? 0.42 : 0.22) : "transparent",
            }}
            aria-label={`${lane.label} at step ${point.stepIndex}`}
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

function buildParameterSeries(steps: OPROStep[]): ParameterSeries[] {
  const byParam = new Map<string, ParameterPoint[]>();
  for (const step of steps) {
    if (step.accepted !== true) continue;
    const points = byParam.get(step.paramPath) ?? [];
    points.push({
      stepIndex: step.stepIndex,
      value: step.candidateValue,
      hash: valueHash(step.candidateValue),
      score: step.score,
    });
    byParam.set(step.paramPath, points);
  }
  return [...byParam.entries()].map(([path, points]) => ({
    path,
    points: points.sort((a, b) => a.stepIndex - b.stepIndex),
  }));
}

function laneValues(points: ParameterPoint[]): Array<{ hash: string; label: string }> {
  const lanes = new Map<string, string>();
  for (const point of points) {
    if (!lanes.has(point.hash)) lanes.set(point.hash, point.value);
  }
  return [...lanes.entries()].map(([hash, label]) => ({ hash, label }));
}

function valueHash(value: string): string {
  let hash = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

export const _oproParameter = {
  buildParameterSeries,
  valueHash,
};
