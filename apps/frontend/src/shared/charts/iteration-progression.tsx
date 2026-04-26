import { cn } from "@/lib/utils";
import { useState } from "react";

export interface IterationEntry {
  iter_index: number;
  phase: string | null;
  score: number | null;
  text: string | null;
  metadata: Record<string, unknown>;
}

interface IterationsResponse {
  iterations: IterationEntry[];
  threshold: number | null;
  converged: boolean | null;
}

const PHASE_STYLES: Record<string, { badge: string; dot: string }> = {
  generate: { badge: "bg-blue-500/15 text-blue-400", dot: "bg-blue-400" },
  verify:   { badge: "bg-green-500/15 text-green-400", dot: "bg-green-400" },
  reflect:  { badge: "bg-amber-500/15 text-amber-400", dot: "bg-amber-400" },
  refine:   { badge: "bg-violet-500/15 text-violet-400", dot: "bg-violet-400" },
};

const DEFAULT_STYLE = { badge: "bg-muted/20 text-muted", dot: "bg-muted" };

function phaseStyle(phase: string | null) {
  return phase ? (PHASE_STYLES[phase] ?? DEFAULT_STYLE) : DEFAULT_STYLE;
}

function parseResponse(data: unknown): IterationsResponse | null {
  if (data == null || typeof data !== "object" || Array.isArray(data)) return null;
  const d = data as Record<string, unknown>;
  if (!Array.isArray(d.iterations)) return null;
  return {
    iterations: d.iterations
      .filter((it): it is Record<string, unknown> => it != null && typeof it === "object")
      .map(
        (it): IterationEntry => ({
          iter_index: typeof it.iter_index === "number" ? it.iter_index : 0,
          phase: typeof it.phase === "string" ? it.phase : null,
          score: typeof it.score === "number" ? it.score : null,
          text: typeof it.text === "string" ? it.text : null,
          metadata:
            it.metadata != null && typeof it.metadata === "object"
              ? (it.metadata as Record<string, unknown>)
              : {},
        }),
      ),
    threshold: typeof d.threshold === "number" ? d.threshold : null,
    converged: typeof d.converged === "boolean" ? d.converged : null,
  };
}

export function IterationProgression({
  data,
  phaseFilter,
}: {
  data: unknown;
  phaseFilter?: string;
}) {
  const resp = parseResponse(data);
  const allEntries = resp?.iterations ?? [];
  const entries = phaseFilter ? allEntries.filter((e) => e.phase === phaseFilter) : allEntries;
  const { threshold, converged } = resp ?? { threshold: null, converged: null };

  if (entries.length === 0) {
    return (
      <div className="text-[11px] text-muted px-2 py-4 text-center">no iteration data</div>
    );
  }

  const convergedIdx =
    threshold != null
      ? entries.find((e) => e.score != null && e.score >= threshold)?.iter_index
      : converged
      ? entries[entries.length - 1]?.iter_index
      : undefined;

  return (
    <ol className="flex flex-col gap-0">
      {entries.map((entry) => (
        <IterationStep
          key={`${entry.iter_index}-${entry.phase}`}
          entry={entry}
          isConverged={entry.iter_index === convergedIdx}
        />
      ))}
    </ol>
  );
}

function IterationStep({
  entry,
  isConverged,
}: {
  entry: IterationEntry;
  isConverged: boolean;
}) {
  const [open, setOpen] = useState(false);
  const style = phaseStyle(entry.phase);
  const hasBody =
    !!entry.text ||
    !!entry.metadata?.critique_summary ||
    entry.metadata?.needs_revision != null;

  return (
    <li
      className={cn(
        "flex gap-3 border-l-2 pl-3 py-2 text-[11px]",
        isConverged ? "border-[var(--color-ok)]" : "border-border",
      )}
    >
      <div className="flex flex-col items-center gap-1 pt-0.5">
        <div className={cn("h-2 w-2 rounded-full shrink-0", style.dot)} />
      </div>
      <div className="flex flex-col gap-1 flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-muted">#{entry.iter_index}</span>
          {entry.phase && (
            <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-medium", style.badge)}>
              {entry.phase}
            </span>
          )}
          {entry.score != null && (
            <span className="font-mono tabular-nums text-text">{entry.score.toFixed(3)}</span>
          )}
          {isConverged && (
            <span className="rounded px-1.5 py-0.5 text-[10px] font-medium bg-[var(--color-ok)]/15 text-[var(--color-ok)]">
              converged
            </span>
          )}
          {hasBody && (
            <button
              className="ml-auto text-muted hover:text-text transition-colors"
              onClick={() => setOpen((v) => !v)}
              type="button"
            >
              {open ? "▲" : "▼"}
            </button>
          )}
        </div>
        {open && hasBody && (
          <div className="mt-1 flex flex-col gap-1">
            {entry.metadata?.needs_revision != null && (
              <div className="text-muted">
                needs revision:{" "}
                <span className="text-text font-medium">
                  {String(entry.metadata.needs_revision)}
                </span>
              </div>
            )}
            {!!entry.metadata?.critique_summary && (
              <p className="text-text/80 whitespace-pre-wrap break-words">
                {String(entry.metadata.critique_summary)}
              </p>
            )}
            {entry.text && (
              <p className="text-text/70 whitespace-pre-wrap break-words font-mono text-[10px]">
                {entry.text}
              </p>
            )}
          </div>
        )}
      </div>
    </li>
  );
}
