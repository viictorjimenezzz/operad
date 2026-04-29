import {
  AdjacentPromptDiff,
  FullValueToggle,
} from "@/components/algorithms/opro/prompt-adjacent-diff";
import { EmptyState } from "@/components/ui";
import { hashColorDim } from "@/lib/hash-color";
import { truncateMiddle } from "@/lib/utils";
import { useEffect, useRef } from "react";

export type ParameterEvolutionPoint = {
  runId: string;
  startedAt: number;
  value: unknown;
  hash: string;
  gradient?: {
    message: string;
    severity: "low" | "medium" | "high";
    targetPaths: string[];
    critic?: { agentPath: string; runId: string; langfuseUrl?: string | null };
  };
  sourceTapeStep?: { epoch: number; batch: number; iter: number };
  langfuseUrl?: string | null;
  metricSnapshot?: Record<string, number>;
};

export interface TextEvolutionProps {
  points: ParameterEvolutionPoint[];
  selectedStep: number | null;
  onSelectStep: (index: number) => void;
}

export function TextEvolution({ points, selectedStep, onSelectStep }: TextEvolutionProps) {
  const rowRefs = useRef<Array<HTMLDivElement | null>>([]);

  useEffect(() => {
    if (selectedStep == null) return;
    rowRefs.current[selectedStep]?.scrollIntoView?.({ block: "nearest" });
  }, [selectedStep]);

  if (points.length === 0) {
    return (
      <EmptyState
        title="no observed values yet"
        description="this text parameter has not emitted any evolution points"
      />
    );
  }

  return (
    <div className="space-y-2">
      {points.map((point, index) => {
        const selected = selectedStep === index;
        const value = textValue(point.value);
        const previous = index > 0 ? textValue(points[index - 1]?.value) : null;
        return (
          <div
            key={`${point.runId}-${point.hash}-${index}`}
            ref={(node) => {
              rowRefs.current[index] = node;
            }}
            data-selected={selected ? "true" : undefined}
            className="border-b border-border px-3 py-2"
            style={{ background: selected ? hashColorDim(point.hash, 0.2) : undefined }}
          >
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <button
                type="button"
                onClick={() => onSelectStep(index)}
                className="min-w-0 text-left"
                aria-label={`select step ${index + 1}`}
              >
                <div className="text-[12px] font-medium text-text">step {index + 1}</div>
                <div className="mt-0.5 flex flex-wrap items-center gap-2 font-mono text-[11px] text-muted">
                  <span>{truncateMiddle(point.runId, 18)}</span>
                  <span>{formatRelative(point.startedAt)}</span>
                  <span>hash {truncateMiddle(point.hash, 12)}</span>
                </div>
              </button>
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
                {point.gradient?.severity ? <span>severity: {point.gradient.severity}</span> : null}
                {point.langfuseUrl ? (
                  <a
                    href={point.langfuseUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="Open trace in Langfuse"
                    className="text-accent hover:underline"
                  >
                    langfuse -&gt;
                  </a>
                ) : null}
              </div>
            </div>

            {previous == null ? (
              <div className="space-y-2">
                <div className="rounded border border-border bg-bg-2 px-2 py-1.5 text-[12px] text-muted">
                  initial value
                </div>
                <FullValueToggle value={value} />
              </div>
            ) : (
              <div className="space-y-1">
                <div className="text-[11px] text-muted">diff vs step {index}</div>
                <AdjacentPromptDiff
                  before={previous}
                  after={value}
                  beforeLabel={`step ${index}`}
                  afterLabel={`step ${index + 1}`}
                />
                <FullValueToggle value={value} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function textValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value == null) return "";
  return JSON.stringify(value, null, 2);
}

function formatRelative(epochSeconds: number): string {
  const delta = Math.max(0, Math.floor(Date.now() / 1000 - epochSeconds));
  if (delta < 60) return `${delta}s ago`;
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
  if (delta < 86400) return `${Math.floor(delta / 3600)}h ago`;
  return `${Math.floor(delta / 86400)}d ago`;
}
