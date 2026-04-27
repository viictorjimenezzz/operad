import { PromptDriftDiff } from "@/components/charts/prompt-drift-diff";
import { KeyValueGrid } from "@/components/ui";
import { formatNumber } from "@/lib/utils";

export function ParameterDiffPanel({
  path,
  previous,
  current,
}: {
  path: string;
  previous: unknown;
  current: unknown;
}) {
  if (
    typeof previous === "string" ||
    typeof current === "string" ||
    Array.isArray(previous) ||
    Array.isArray(current)
  ) {
    return (
      <div className="rounded-lg border border-border bg-bg-1 p-3">
        <PromptDriftDiff
          before={stringifyValue(previous)}
          after={stringifyValue(current)}
          selectedPath={path}
        />
      </div>
    );
  }

  if (typeof previous === "number" || typeof current === "number") {
    const before = typeof previous === "number" ? previous : null;
    const after = typeof current === "number" ? current : null;
    const delta = before != null && after != null ? after - before : null;
    return (
      <div className="rounded-lg border border-border bg-bg-1 p-3 text-[13px] text-text">
        <span className="font-mono">{formatNumber(before)}</span>
        <span className="px-2 text-muted">to</span>
        <span className="font-mono">{formatNumber(after)}</span>
        {delta != null ? <span className="ml-2 text-muted">({formatNumber(delta)})</span> : null}
      </div>
    );
  }

  if (isRecord(previous) || isRecord(current)) {
    const before = isRecord(previous) ? previous : {};
    const after = isRecord(current) ? current : {};
    const keys = [...new Set([...Object.keys(before), ...Object.keys(after)])].sort();
    return (
      <div className="rounded-lg border border-border bg-bg-1 p-3">
        <KeyValueGrid
          density="compact"
          rows={keys.map((key) => ({
            key,
            value: `${stringifyValue(before[key])} -> ${stringifyValue(after[key])}`,
            mono: true,
          }))}
        />
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-bg-1 p-3 font-mono text-[12px] text-text">
      {stringifyValue(previous)} -&gt; {stringifyValue(current)}
    </div>
  );
}

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
