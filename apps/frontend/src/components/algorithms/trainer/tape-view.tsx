import { EmptyState } from "@/components/ui";
import { hashColor } from "@/lib/hash-color";
import { cn, formatDurationMs } from "@/lib/utils";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useMemo, useRef } from "react";
import { useSearchParams } from "react-router-dom";

interface TrainerTapeViewProps {
  runId?: string;
  dataTape?: unknown;
}

type TapeRow = {
  id: string;
  agentPath: string;
  inputHash: string | null;
  outputHash: string | null;
  latencyMs: number | null;
  inTapeForStep: string;
  severityScore: number | null;
  severityLabel: string;
  langfuseUrl: string | null;
  paramPath: string | null;
  stepIndex: number | null;
};

const ROW_HEIGHT = 22;
const GRID_TEMPLATE =
  "minmax(220px,1.6fr) minmax(130px,1fr) minmax(130px,1fr) minmax(96px,0.7fr) minmax(130px,1fr) minmax(120px,0.9fr) minmax(86px,0.5fr)";

export function TrainerTapeView({ runId, dataTape }: TrainerTapeViewProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const rows = useMemo(() => normalizeRows(dataTape), [dataTape]);
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => viewportRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 12,
  });
  const virtualItems = virtualizer.getVirtualItems();
  const renderedRows =
    virtualItems.length > 0
      ? virtualItems
      : rows.map((_, index) => ({
          index,
          key: index,
          size: ROW_HEIGHT,
          start: index * ROW_HEIGHT,
        }));

  if (rows.length === 0) {
    return (
      <div className="h-full overflow-auto p-4">
        <EmptyState
          title="no tape entries recorded"
          description="tape capture is not enabled for this run; wrap `Trainer.fit` inside `async with operad.optim.backprop.tape():`"
        />
      </div>
    );
  }

  const selectedParam = searchParams.get("param");
  const selectedStepRaw = searchParams.get("step");
  const selectedStep = selectedStepRaw == null ? null : Number(selectedStepRaw);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden p-4">
      <div className="overflow-hidden rounded-lg border border-border bg-bg-1">
        <div
          className="grid min-h-7 items-center gap-2 border-b border-border bg-bg-2/95 px-3 text-[10px] font-medium uppercase tracking-[0.06em] text-muted-2"
          style={{ gridTemplateColumns: GRID_TEMPLATE }}
        >
          <span>agent path</span>
          <span>input hash</span>
          <span>output hash</span>
          <span>latency</span>
          <span>in tape step</span>
          <span>gradient sev</span>
          <span>langfuse -&gt;</span>
        </div>
        <div ref={viewportRef} aria-label="trainer tape rows" className="max-h-[560px] overflow-auto">
          <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
            {renderedRows.map((virtualRow) => {
              const row = rows[virtualRow.index];
              if (!row) return null;
              const selected =
                row.paramPath !== null &&
                selectedParam === row.paramPath &&
                (selectedStep == null || selectedStep === row.stepIndex);
              return (
                <button
                  key={`${row.id}:${virtualRow.index}`}
                  type="button"
                  data-testid="tape-row"
                  aria-label={`open tape entry ${row.agentPath}`}
                  onClick={() => {
                    if (!row.paramPath) return;
                    const paramPath = row.paramPath;
                    setSearchParams((current) => {
                      const next = new URLSearchParams(current);
                      next.set("tab", "parameters");
                      next.set("param", paramPath);
                      if (row.stepIndex != null) next.set("step", String(row.stepIndex));
                      else next.delete("step");
                      return next;
                    });
                  }}
                  className={cn(
                    "absolute left-0 grid h-[var(--row-h-tight)] w-full items-center gap-2 border-b border-border px-3 text-left text-[12px] transition-colors",
                    row.paramPath ? "cursor-pointer hover:bg-bg-2/45" : "cursor-default",
                    selected && "bg-bg-2/45",
                  )}
                  style={{
                    top: 0,
                    transform: `translateY(${virtualRow.start}px)`,
                    height: `${virtualRow.size}px`,
                    gridTemplateColumns: GRID_TEMPLATE,
                  }}
                >
                  <span className="truncate font-mono text-[11px] text-text" title={row.agentPath}>
                    {row.agentPath}
                  </span>
                  <HashCell value={row.inputHash} />
                  <HashCell value={row.outputHash} />
                  <span className="font-mono text-[11px] text-text">
                    {row.latencyMs == null ? "-" : formatDurationMs(row.latencyMs)}
                  </span>
                  <span className="truncate font-mono text-[11px] text-muted" title={row.inTapeForStep}>
                    {row.inTapeForStep}
                  </span>
                  <SeverityCell score={row.severityScore} label={row.severityLabel} />
                  {row.langfuseUrl ? (
                    <a
                      href={row.langfuseUrl}
                      className="font-mono text-[11px] text-accent hover:text-[--color-accent-strong]"
                      onClick={(event) => event.stopPropagation()}
                      title={row.langfuseUrl}
                    >
                      open
                    </a>
                  ) : (
                    <span className="font-mono text-[11px] text-muted-2">-</span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>
      <div className="mt-2 px-1 font-mono text-[11px] text-muted-2">
        {rows.length} entries{runId ? ` · ${runId}` : ""}
      </div>
    </div>
  );
}

function HashCell({ value }: { value: string | null }) {
  if (!value) return <span className="font-mono text-[11px] text-muted-2">-</span>;
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-text">
      <span aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ background: hashColor(value) }} />
      <span className="truncate">{value}</span>
    </span>
  );
}

function SeverityCell({ score, label }: { score: number | null; label: string }) {
  const normalized = score == null ? null : Math.max(0, Math.min(1, (score + 1) / 2));
  const width = normalized == null ? 0 : normalized * 100;
  const tone =
    score == null
      ? "var(--color-muted-2)"
      : score < -0.33
        ? "var(--color-err)"
        : score < 0.33
          ? "var(--color-warn)"
          : "var(--color-ok)";
  return (
    <span className="inline-flex min-w-0 items-center gap-2">
      <span className="w-12 text-right font-mono text-[11px] text-text">{label}</span>
      <span className="h-1 w-full rounded-full bg-bg-3">
        <span aria-label="severity bar" className="block h-1 rounded-full" style={{ width: `${width}%`, background: tone }} />
      </span>
    </span>
  );
}

function normalizeRows(dataTape: unknown): TapeRow[] {
  const entries = rawEntries(dataTape);
  return entries.map((entry, index) => {
    const agentPath =
      stringValue(entry, ["agent_path", "path", "agentPath"]) ?? `entry ${index + 1}`;
    const inputHash =
      stringValue(entry, ["input_hash", "hash_input", "inputHash"]) ??
      stringValue(entry.metadata, ["input_hash", "hash_input"]);
    const outputHash =
      stringValue(entry, ["output_hash", "hash_output", "outputHash"]) ??
      stringValue(entry.metadata, ["output_hash", "hash_output"]);
    const latencyMs = latencyFor(entry);
    const paramPath = parameterPathFor(entry);
    const stepIndex = stepIndexFor(entry);
    const step = tapeStepFor(entry);
    const severity = severityFor(entry);

    return {
      id: stringValue(entry, ["event_id", "id"]) ?? `${index}`,
      agentPath,
      inputHash,
      outputHash,
      latencyMs,
      inTapeForStep: step,
      severityScore: severity.score,
      severityLabel: severity.label,
      langfuseUrl: stringValue(entry, ["langfuse_url", "langfuseUrl"]),
      paramPath,
      stepIndex,
    };
  });
}

type TapeEntry = {
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
};

function rawEntries(dataTape: unknown): TapeEntry[] {
  if (Array.isArray(dataTape)) {
    return dataTape.filter((row): row is TapeEntry => isRecord(row));
  }
  if (!isRecord(dataTape)) return [];
  const entries = dataTape.entries;
  if (!Array.isArray(entries)) return [];
  return entries.filter((row): row is TapeEntry => isRecord(row));
}

function latencyFor(entry: TapeEntry): number | null {
  const msDirect = numberValue(entry, ["latency_ms", "latencyMs"]);
  if (msDirect != null) return msDirect;
  const latency = numberValue(entry, ["latency"]);
  if (latency != null) return latency > 1000 ? latency : latency * 1000;
  const startedAt = numberValue(entry, ["started_at", "startedAt"]);
  const finishedAt = numberValue(entry, ["finished_at", "finishedAt"]);
  if (startedAt != null && finishedAt != null && finishedAt >= startedAt) {
    return (finishedAt - startedAt) * 1000;
  }
  return null;
}

function tapeStepFor(entry: TapeEntry): string {
  const stepRecord = stepRecordFor(entry);
  if (!stepRecord) return "-";
  const parts: string[] = [];
  const epoch = numberValue(stepRecord, ["epoch"]);
  const batch = numberValue(stepRecord, ["batch"]);
  const iter = numberValue(stepRecord, ["iter"]);
  const optimizerStep =
    numberValue(stepRecord, ["optimizer_step"]) ?? numberValue(stepRecord, ["optimizerStep"]);
  if (epoch != null) parts.push(`e${Math.trunc(epoch)}`);
  if (batch != null) parts.push(`b${Math.trunc(batch)}`);
  if (iter != null) parts.push(`i${Math.trunc(iter)}`);
  if (optimizerStep != null) parts.push(`s${Math.trunc(optimizerStep)}`);
  return parts.length > 0 ? parts.join(" · ") : "-";
}

function parameterPathFor(entry: TapeEntry): string | null {
  const direct =
    stringValue(entry, ["param_path", "parameter_path", "parameterPath", "full_path"]) ??
    stringValue(entry, ["target_path", "targetPath"]);
  if (direct) return direct;
  const paths =
    stringArray(entry, ["target_paths", "targetPaths"]) ??
    stringArray(entry.gradient, ["target_paths", "targetPaths"]);
  return paths?.[0] ?? null;
}

function stepIndexFor(entry: TapeEntry): number | null {
  const direct =
    numberValue(entry, ["step"]) ??
    numberValue(entry, ["step_index", "stepIndex"]) ??
    numberValue(entry, ["parameter_step", "parameterStep"]);
  if (direct != null) return Math.trunc(direct);
  const stepRecord = stepRecordFor(entry);
  if (!stepRecord) return null;
  const optimizerStep =
    numberValue(stepRecord, ["optimizer_step"]) ?? numberValue(stepRecord, ["optimizerStep"]);
  if (optimizerStep != null) return Math.trunc(optimizerStep);
  return null;
}

function severityFor(entry: TapeEntry): { score: number | null; label: string } {
  const raw =
    entry.gradient_severity ??
    entry.severity ??
    (isRecord(entry.gradient) ? entry.gradient.severity : undefined);
  if (typeof raw === "number" && Number.isFinite(raw)) {
    const score = Math.max(-1, Math.min(1, raw));
    return { score, label: score.toFixed(2) };
  }
  if (typeof raw !== "string") return { score: null, label: "-" };
  const value = raw.toLowerCase();
  if (value === "high") return { score: -1, label: "high" };
  if (value === "medium") return { score: 0, label: "medium" };
  if (value === "low") return { score: 1, label: "low" };
  return { score: null, label: raw };
}

function stepRecordFor(entry: TapeEntry): Record<string, unknown> | null {
  const raw = entry.in_tape_for_step ?? entry.tape_link ?? entry.source_tape_step;
  return isRecord(raw) ? raw : null;
}

function stringValue(
  input: unknown,
  keys: string[],
): string | null {
  if (!isRecord(input)) return null;
  for (const key of keys) {
    const value = input[key];
    if (typeof value === "string" && value.length > 0) return value;
  }
  return null;
}

function numberValue(
  input: unknown,
  keys: string[],
): number | null {
  if (!isRecord(input)) return null;
  for (const key of keys) {
    const value = input[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return null;
}

function stringArray(input: unknown, keys: string[]): string[] | null {
  if (!isRecord(input)) return null;
  for (const key of keys) {
    const value = input[key];
    if (!Array.isArray(value)) continue;
    const out = value.filter((item): item is string => typeof item === "string" && item.length > 0);
    if (out.length > 0) return out;
  }
  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
