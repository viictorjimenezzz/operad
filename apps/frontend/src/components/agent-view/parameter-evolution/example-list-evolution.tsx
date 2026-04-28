import { EmptyState, FieldTree } from "@/components/ui";
import { hashColor, hashColorDim } from "@/lib/hash-color";
import { truncateMiddle } from "@/lib/utils";
import { useMemo, useState } from "react";

import type { ParameterEvolutionPoint } from "./text-evolution";

export interface ExampleListEvolutionProps {
  points: ParameterEvolutionPoint[];
  selectedStep: number | null;
  onSelectStep: (index: number) => void;
}

type ExampleRow = {
  hash: string;
  label: string;
  input: unknown;
  output: unknown;
};

type ExpandedCell = {
  hash: string;
  step: number;
} | null;

export function ExampleListEvolution({
  points,
  selectedStep,
  onSelectStep,
}: ExampleListEvolutionProps) {
  const steps = useMemo(() => points.map((point) => normalizeExamples(point.value)), [points]);
  const rows = useMemo(() => collectRows(steps), [steps]);
  const [expanded, setExpanded] = useState<ExpandedCell>(null);
  const expandedRow = expanded
    ? (steps[expanded.step]?.find((example) => example.hash === expanded.hash) ?? null)
    : null;

  if (points.length === 0) {
    return (
      <EmptyState
        title="no observed values yet"
        description="this example list has not emitted any evolution points"
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="overflow-auto">
        <div
          className="grid min-w-[620px] gap-1"
          style={{
            gridTemplateColumns: `minmax(200px, 1.5fr) repeat(${Math.max(
              points.length,
              1,
            )}, minmax(44px, 1fr))`,
          }}
        >
          <span />
          {points.map((point, index) => (
            <div
              key={`${point.runId}-head`}
              className="flex min-h-7 flex-col items-center justify-center gap-0.5 px-1"
            >
              <button
                type="button"
                onClick={() => onSelectStep(index)}
                className="truncate text-center font-mono text-[10px] text-muted-2 hover:text-text"
                aria-label={`select step ${index + 1}`}
              >
                {index + 1}
              </button>
              {point.langfuseUrl ? (
                <a
                  href={point.langfuseUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Open trace in Langfuse"
                  className="text-[9px] text-accent hover:underline"
                >
                  lf
                </a>
              ) : null}
            </div>
          ))}
          {rows.map((row) => (
            <ExampleLifelineRow
              key={row.hash}
              row={row}
              steps={steps}
              expanded={expanded}
              onSelect={(step) => {
                onSelectStep(step);
                setExpanded({ hash: row.hash, step });
              }}
            />
          ))}
        </div>
      </div>
      {expanded && expandedRow ? (
        <div className="border-t border-border pt-2">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-[12px]">
            <span className="font-medium text-text">step {expanded.step + 1} example</span>
            <span className="font-mono text-muted">{truncateMiddle(expanded.hash, 12)}</span>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="min-w-0 border-l border-border pl-2">
              <div className="mb-1 text-[11px] text-muted">input</div>
              <FieldTree
                data={expandedRow.input}
                defaultDepth={2}
                hideCopy
                truncateStrings={false}
              />
            </div>
            <div className="min-w-0 border-l border-border pl-2">
              <div className="mb-1 text-[11px] text-muted">output</div>
              <FieldTree
                data={expandedRow.output}
                defaultDepth={2}
                hideCopy
                truncateStrings={false}
              />
            </div>
          </div>
        </div>
      ) : selectedStep != null ? (
        <div className="border-t border-border pt-2 text-[12px] text-muted">
          click an example cell to inspect input and output
        </div>
      ) : null}
    </div>
  );
}

function ExampleLifelineRow({
  row,
  steps,
  expanded,
  onSelect,
}: {
  row: ExampleRow;
  steps: ExampleRow[][];
  expanded: ExpandedCell;
  onSelect: (step: number) => void;
}) {
  return (
    <>
      <div className="min-w-0 truncate px-2 py-1.5 text-[12px] text-text" title={row.label}>
        {truncateMiddle(row.label, 44)}
      </div>
      {steps.map((stepExamples, index) => {
        const present = stepExamples.some((example) => example.hash === row.hash);
        const selected = expanded?.hash === row.hash && expanded.step === index;
        return (
          <button
            key={`${row.hash}-${index}`}
            type="button"
            onClick={() => {
              if (present) onSelect(index);
            }}
            className="flex h-7 items-center justify-center border border-border bg-bg-1 hover:border-border-strong disabled:cursor-default disabled:hover:border-border"
            title={row.label}
            disabled={!present}
            aria-label={`example ${row.label} ${present ? "present" : "absent"} at step ${
              index + 1
            }`}
          >
            {present ? (
              <span
                className="h-3 w-7"
                style={{
                  background: hashColorDim(row.hash, selected ? 0.65 : 0.45),
                  borderTopColor: hashColor(row.hash),
                  borderTopStyle: "solid",
                  borderTopWidth: 2,
                }}
              />
            ) : (
              <span className="h-px w-7 bg-border-strong" />
            )}
          </button>
        );
      })}
    </>
  );
}

function normalizeExamples(value: unknown): ExampleRow[] {
  if (!Array.isArray(value)) return [];
  return value.map((item, index) => {
    const record = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
    const input = record.input ?? record.inputs ?? record.question ?? record.prompt ?? null;
    const output = record.output ?? record.outputs ?? record.answer ?? record.response ?? null;
    const label = exampleLabel(input, output, index);
    const hash = stableHash(stableStringify({ input, output, raw: item }));
    return { hash, label, input, output };
  });
}

function collectRows(steps: ExampleRow[][]): ExampleRow[] {
  const rows = new Map<string, ExampleRow>();
  for (const examples of steps) {
    for (const example of examples) {
      if (!rows.has(example.hash)) rows.set(example.hash, example);
    }
  }
  return [...rows.values()];
}

function exampleLabel(input: unknown, output: unknown, index: number): string {
  const raw = input ?? output;
  if (typeof raw === "string" && raw.length > 0) return raw;
  if (raw != null) return stableStringify(raw);
  return `example ${index + 1}`;
}

function stableHash(value: string): string {
  let h = 0;
  for (let i = 0; i < value.length; i += 1) h = (h * 31 + value.charCodeAt(i)) | 0;
  return Math.abs(h).toString(16).padStart(8, "0");
}

function stableStringify(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  return `{${Object.entries(value as Record<string, unknown>)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, val]) => `${JSON.stringify(key)}:${stableStringify(val)}`)
    .join(",")}}`;
}
