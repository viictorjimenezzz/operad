import { EmptyState } from "@/components/ui";
import { hashColor, hashColorDim } from "@/lib/hash-color";
import { truncateMiddle } from "@/lib/utils";
import { useMemo } from "react";

import type { ParameterEvolutionPoint } from "./text-evolution";

export interface RuleListEvolutionProps {
  points: ParameterEvolutionPoint[];
  selectedStep: number | null;
  onSelectStep: (index: number) => void;
}

type RuleRow = {
  hash: string;
  text: string;
};

export function RuleListEvolution({ points, selectedStep, onSelectStep }: RuleListEvolutionProps) {
  const steps = useMemo(() => points.map((point) => normalizeRules(point.value)), [points]);
  const rows = useMemo(() => collectRows(steps), [steps]);
  const selected = selectedStep ?? 0;

  if (points.length === 0) {
    return (
      <EmptyState
        title="no observed values yet"
        description="this rule list has not emitted any evolution points"
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="overflow-auto">
        <div
          className="grid min-w-[560px] gap-1"
          style={{
            gridTemplateColumns: `minmax(180px, 1.4fr) repeat(${Math.max(
              points.length,
              1,
            )}, minmax(44px, 1fr))`,
          }}
        >
          <span />
          {points.map((point, index) => (
            <button
              key={`${point.runId}-head`}
              type="button"
              onClick={() => onSelectStep(index)}
              className="truncate px-1 text-center font-mono text-[10px] text-muted-2 hover:text-text"
              aria-label={`select step ${index + 1}`}
            >
              {index + 1}
            </button>
          ))}
          {rows.map((row) => (
            <RuleLifelineRow key={row.hash} row={row} steps={steps} onSelectStep={onSelectStep} />
          ))}
        </div>
      </div>
      <SelectedRuleList steps={steps} selectedStep={selected} />
    </div>
  );
}

function RuleLifelineRow({
  row,
  steps,
  onSelectStep,
}: {
  row: RuleRow;
  steps: RuleRow[][];
  onSelectStep: (index: number) => void;
}) {
  return (
    <>
      <div className="min-w-0 truncate px-2 py-1.5 text-[12px] text-text" title={row.text}>
        {truncateMiddle(row.text, 42)}
      </div>
      {steps.map((stepRules, index) => {
        const present = stepRules.some((rule) => rule.hash === row.hash);
        return (
          <button
            key={`${row.hash}-${index}`}
            type="button"
            onClick={() => onSelectStep(index)}
            className="flex h-7 items-center justify-center border border-border bg-bg-1 hover:border-border-strong"
            title={row.text}
            aria-label={`rule ${row.text} ${present ? "present" : "absent"} at step ${index + 1}`}
          >
            {present ? (
              <span
                className="h-3 w-7"
                style={{
                  background: hashColorDim(row.hash, 0.55),
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

function SelectedRuleList({
  steps,
  selectedStep,
}: {
  steps: RuleRow[][];
  selectedStep: number;
}) {
  const current = steps[selectedStep] ?? steps[0] ?? [];
  const previous = selectedStep > 0 ? (steps[selectedStep - 1] ?? []) : [];
  const previousHashes = new Set(previous.map((rule) => rule.hash));
  const currentHashes = new Set(current.map((rule) => rule.hash));
  const removed = previous.filter((rule) => !currentHashes.has(rule.hash));

  return (
    <div className="border-t border-border pt-2">
      <div className="mb-1 text-[12px] font-medium text-text">step {selectedStep + 1} rules</div>
      {current.length === 0 && removed.length === 0 ? (
        <div className="text-[12px] text-muted">empty rule list</div>
      ) : (
        <ol className="m-0 space-y-1 pl-5 text-[12px]">
          {current.map((rule) => {
            const added = selectedStep > 0 && !previousHashes.has(rule.hash);
            return (
              <li key={rule.hash} className={added ? "text-[--color-ok]" : "text-text"}>
                {rule.text}
              </li>
            );
          })}
          {removed.map((rule) => (
            <li key={`removed-${rule.hash}`} className="text-muted line-through">
              {rule.text}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function normalizeRules(value: unknown): RuleRow[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => {
    const text = typeof item === "string" ? item : stableStringify(item);
    return { text, hash: stableHash(text) };
  });
}

function collectRows(steps: RuleRow[][]): RuleRow[] {
  const rows = new Map<string, RuleRow>();
  for (const rules of steps) {
    for (const rule of rules) {
      if (!rows.has(rule.hash)) rows.set(rule.hash, rule);
    }
  }
  return [...rows.values()];
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
