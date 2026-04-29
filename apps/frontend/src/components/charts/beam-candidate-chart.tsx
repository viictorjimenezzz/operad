import { EmptyState } from "@/components/ui/empty-state";
import { type RunRow, RunTable, type RunTableColumn } from "@/components/ui/run-table";
import { beamCandidateDetails } from "@/lib/beam-data";
import { Candidate } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useState } from "react";
import { z } from "zod";

const CandidateArray = z.array(Candidate);

const selectedColumns: RunTableColumn[] = [
  { id: "candidate", label: "Candidate", source: "candidate", sortable: true, width: 92 },
  { id: "rank", label: "Rank", source: "rank", sortable: true, align: "right", width: 64 },
  { id: "score", label: "Score", source: "score", sortable: true, width: 150 },
  { id: "prompt", label: "Prompt", source: "prompt", width: "1fr" },
  { id: "answer", label: "Answer diff", source: "answer", width: "1fr" },
  { id: "rationale", label: "Judge rationale", source: "rationale", width: "1fr" },
  { id: "latency", label: "Latency", source: "latency", sortable: true, align: "right", width: 88 },
  { id: "cost", label: "Cost", source: "cost", sortable: true, align: "right", width: 78 },
  { id: "langfuse", label: "Langfuse", source: "langfuse", width: 84 },
];

export function BeamCandidateChart({
  data,
  iterationsData,
  dataEvents,
  dataChildren,
  dataAgentsSummary,
  runId = "beam",
  height = 220,
}: {
  data: unknown;
  iterationsData?: unknown;
  dataEvents?: unknown;
  dataChildren?: unknown;
  dataAgentsSummary?: unknown;
  runId?: string;
  height?: number;
}) {
  const parsed = CandidateArray.safeParse(data);
  const [selectedCandidateIndex, setSelectedCandidateIndex] = useState<number | null>(null);
  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no beam candidates" />;
  }

  const details = beamCandidateDetails(
    parsed.data,
    iterationsData,
    dataEvents,
    dataChildren,
    dataAgentsSummary,
  );
  if (details.length === 0) {
    return <EmptyState title="no beam candidates" />;
  }

  const selectedIndex = selectedCandidateIndex ?? details[0]?.candidateIndex ?? 0;
  const selected = details.find((detail) => detail.candidateIndex === selectedIndex) ?? details[0];
  const selectedRows = selected ? [toSelectedRow(selected, runId)] : [];

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-4">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
        <div className="rounded-lg border border-border bg-bg-1 p-3">
          <div className="mb-2 flex items-center justify-between gap-3">
            <div>
              <div className="text-[13px] font-medium text-text">Candidate scores</div>
              <div className="text-[11px] text-muted">click a point to inspect the invocation</div>
            </div>
            <span className="font-mono text-[11px] text-muted-2">{details.length} candidates</span>
          </div>
          <CandidateScatter
            details={details}
            selectedCandidateIndex={selectedIndex}
            onSelect={setSelectedCandidateIndex}
            height={height}
          />
        </div>
        <div className="rounded-lg border border-border bg-bg-1 p-3">
          <div className="mb-2">
            <div className="text-[13px] font-medium text-text">Score histogram</div>
            <div className="text-[11px] text-muted">candidate count by score bucket</div>
          </div>
          <ScoreHistogram scores={details.map((detail) => detail.candidate.score)} />
        </div>
      </div>
      <RunTable
        rows={selectedRows}
        columns={selectedColumns}
        storageKey={`beam-candidates-selected:${runId}`}
        emptyTitle="no selected candidate"
        emptyDescription="click a score point to inspect its prompt, answer, and judge rationale"
      />
    </div>
  );
}

function CandidateScatter({
  details,
  selectedCandidateIndex,
  onSelect,
  height,
}: {
  details: ReturnType<typeof beamCandidateDetails>;
  selectedCandidateIndex: number;
  onSelect: (candidateIndex: number) => void;
  height: number;
}) {
  const width = 720;
  const padding = { top: 18, right: 20, bottom: 34, left: 44 };
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;
  const candidateIndices = details.map((detail) => detail.candidateIndex);
  const scores = details
    .map((detail) => detail.candidate.score)
    .filter((score): score is number => typeof score === "number" && Number.isFinite(score));
  const xMin = Math.min(...candidateIndices);
  const xMax = Math.max(...candidateIndices);
  const yMin = 0;
  const yMax = Math.max(1, ...scores);
  const xSpan = Math.max(xMax - xMin, 1);
  const ySpan = Math.max(yMax - yMin, 1e-9);

  const xToPx = (x: number) => padding.left + ((x - xMin) / xSpan) * innerW;
  const yToPx = (y: number) => padding.top + (1 - (y - yMin) / ySpan) * innerH;
  const yTicks = [0, 0.25, 0.5, 0.75, 1].filter((tick) => tick <= yMax);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      style={{ height }}
      role="img"
      aria-label="beam candidate score scatter plot"
    >
      <title>Beam candidate score scatter plot</title>
      {yTicks.map((tick) => (
        <g key={tick}>
          <line
            x1={padding.left}
            x2={width - padding.right}
            y1={yToPx(tick)}
            y2={yToPx(tick)}
            stroke="var(--color-border)"
            strokeDasharray="3 3"
          />
          <text
            x={padding.left - 8}
            y={yToPx(tick) + 4}
            textAnchor="end"
            fill="currentColor"
            className="text-[10px] text-muted"
          >
            {tick.toFixed(2)}
          </text>
        </g>
      ))}
      <line
        x1={padding.left}
        x2={width - padding.right}
        y1={height - padding.bottom}
        y2={height - padding.bottom}
        stroke="var(--color-border)"
      />
      <line
        x1={padding.left}
        x2={padding.left}
        y1={padding.top}
        y2={height - padding.bottom}
        stroke="var(--color-border)"
      />
      {details.map((detail) => {
        const selected = detail.candidateIndex === selectedCandidateIndex;
        const score = detail.candidate.score ?? 0;
        return (
          <circle
            key={detail.candidateIndex}
            role="button"
            tabIndex={0}
            aria-label={`select candidate ${detail.candidateIndex}`}
            cx={xToPx(detail.candidateIndex)}
            cy={yToPx(score)}
            r={selected ? 6 : 4.5}
            className={cn("cursor-pointer outline-none", selected && "drop-shadow")}
            fill={
              selected
                ? "var(--color-accent)"
                : detail.selected
                  ? "var(--color-ok)"
                  : "var(--color-muted-2)"
            }
            stroke="var(--color-bg)"
            strokeWidth={selected ? 2 : 1}
            onClick={() => onSelect(detail.candidateIndex)}
            onKeyDown={(event) => {
              if (event.key !== "Enter" && event.key !== " ") return;
              event.preventDefault();
              onSelect(detail.candidateIndex);
            }}
          >
            <title>{`candidate ${detail.candidateIndex}: score ${score.toFixed(3)}`}</title>
          </circle>
        );
      })}
      {details.map((detail) => (
        <text
          key={`x-${detail.candidateIndex}`}
          x={xToPx(detail.candidateIndex)}
          y={height - 14}
          textAnchor="middle"
          fill="currentColor"
          className="text-[10px] text-muted"
        >
          {detail.candidateIndex}
        </text>
      ))}
      <text
        x={width - padding.right}
        y={height - 2}
        textAnchor="end"
        fill="currentColor"
        className="text-[10px] text-muted"
      >
        candidate
      </text>
      <text x={4} y={12} fill="currentColor" className="text-[10px] text-muted">
        score
      </text>
    </svg>
  );
}

function ScoreHistogram({ scores }: { scores: Array<number | null> }) {
  const values = scores.filter(
    (score): score is number => typeof score === "number" && Number.isFinite(score),
  );
  if (values.length === 0) {
    return (
      <div className="flex h-56 items-center justify-center text-[11px] text-muted">no scores</div>
    );
  }

  const bins = buildHistogram(values, 8);
  const maxCount = Math.max(1, ...bins.map((bin) => bin.count));
  const width = 360;
  const height = 220;
  const padding = { top: 12, right: 12, bottom: 34, left: 34 };
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;
  const barW = innerW / bins.length;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      style={{ height }}
      role="img"
      aria-label="score histogram"
    >
      <title>Score histogram</title>
      <line
        x1={padding.left}
        x2={width - padding.right}
        y1={height - padding.bottom}
        y2={height - padding.bottom}
        stroke="var(--color-border)"
      />
      <line
        x1={padding.left}
        x2={padding.left}
        y1={padding.top}
        y2={height - padding.bottom}
        stroke="var(--color-border)"
      />
      {bins.map((bin, index) => {
        const barH = Math.max(3, (bin.count / maxCount) * innerH);
        const x = padding.left + index * barW + 3;
        const y = height - padding.bottom - barH;
        return (
          <g key={`${bin.min}-${bin.max}`}>
            <rect
              x={x}
              y={y}
              width={Math.max(1, barW - 6)}
              height={barH}
              rx={2}
              fill="var(--color-accent)"
              opacity={0.78}
            >
              <title>{`${bin.min.toFixed(2)}-${bin.max.toFixed(2)}: ${bin.count}`}</title>
            </rect>
            <text
              x={x + barW / 2 - 3}
              y={height - 16}
              textAnchor="middle"
              fill="currentColor"
              className="text-[9px] text-muted"
            >
              {bin.min.toFixed(2)}
            </text>
          </g>
        );
      })}
      <text
        x={width - padding.right}
        y={height - 2}
        textAnchor="end"
        fill="currentColor"
        className="text-[10px] text-muted"
      >
        score
      </text>
      <text x={4} y={12} fill="currentColor" className="text-[10px] text-muted">
        count
      </text>
    </svg>
  );
}

function toSelectedRow(
  detail: ReturnType<typeof beamCandidateDetails>[number],
  runId: string,
): RunRow {
  return {
    id: `candidate-${detail.candidateIndex}`,
    identity: `${runId}:${detail.candidateIndex}`,
    state: "ended",
    startedAt:
      detail.generator?.startedAt ?? detail.critic?.startedAt ?? detail.candidate.timestamp,
    endedAt:
      detail.critic?.finishedAt ?? detail.generator?.finishedAt ?? detail.candidate.timestamp,
    durationMs: detail.totalLatencyMs,
    fields: {
      candidate: { kind: "num", value: detail.candidateIndex, format: "int" },
      rank: { kind: "num", value: detail.rank, format: "int" },
      score: { kind: "score", value: detail.candidate.score, min: 0, max: 1 },
      prompt: { kind: "diff", value: detail.prompt || "-" },
      answer: {
        kind: "diff",
        value: detail.answer || "-",
        ...(detail.previousText ? { previous: detail.previousText } : {}),
      },
      rationale: { kind: "diff", value: detail.rationale || "-" },
      latency: { kind: "num", value: detail.totalLatencyMs, format: "ms" },
      cost: { kind: "num", value: detail.costUsd, format: "cost" },
      langfuse: detail.langfuseUrl
        ? { kind: "link", label: "open", to: detail.langfuseUrl }
        : { kind: "text", value: "-", mono: true },
    },
  };
}

function buildHistogram(
  values: number[],
  count: number,
): Array<{ min: number; max: number; count: number }> {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = (max - min || 1) / count;
  const bins = Array.from({ length: count }, (_, index) => ({
    min: min + index * width,
    max: min + (index + 1) * width,
    count: 0,
  }));
  for (const value of values) {
    const index = Math.min(Math.floor((value - min) / width), bins.length - 1);
    const bin = bins[index];
    if (bin) bin.count += 1;
  }
  return bins;
}
