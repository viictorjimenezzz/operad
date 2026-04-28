import { EmptyState } from "@/components/ui/empty-state";
import { GradientEntry } from "@/lib/types";
import { useState } from "react";
import { z } from "zod";

const Schema = z.array(GradientEntry);

const severityClass = {
  high: "border-err bg-err-dim text-err",
  medium: "border-warn bg-warn-dim text-warn",
  low: "border-accent bg-accent-dim text-accent",
  info: "bg-bg-3 text-muted border-border",
};

function severityLabel(severity: number): keyof typeof severityClass {
  if (severity >= 0.75) return "high";
  if (severity >= 0.4) return "medium";
  if (severity > 0.0) return "low";
  return "info";
}

function badge(severity: number) {
  return severityClass[severityLabel(severity)];
}

export function GradientLog({ data }: { data: unknown }) {
  const parsed = Schema.safeParse(data);
  const [filter, setFilter] = useState("");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  if (!parsed.success || parsed.data.length === 0) {
    return (
      <EmptyState
        title="no gradient events"
        description="Trainer does not yet emit TextualGradient data"
      />
    );
  }

  const q = filter.toLowerCase();
  const entries = [...parsed.data]
    .sort((a, b) => b.epoch - a.epoch || b.batch - a.batch)
    .filter(
      (e) =>
        !q ||
        e.message.toLowerCase().includes(q) ||
        e.target_paths.some((p) => p.toLowerCase().includes(q)) ||
        e.applied_diff.toLowerCase().includes(q),
    );

  function toggleExpand(i: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }

  return (
    <div className="flex flex-col gap-2">
      <input
        className="rounded border border-border bg-bg-2 px-2 py-1 text-xs placeholder:text-muted"
        placeholder="filter by message or field…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      {entries.length === 0 ? (
        <div className="text-xs text-muted">no matching entries</div>
      ) : (
        <ol className="flex flex-col gap-2 text-xs">
          {entries.map((entry, i) => (
            <li key={i} className="rounded-md border border-border bg-bg-2 px-3 py-2">
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="text-[0.68rem] uppercase tracking-[0.08em] text-muted">
                  epoch {entry.epoch} · batch {entry.batch}
                </span>
                <span
                  className={`rounded border px-1.5 py-0.5 text-[10px] ${badge(entry.severity)}`}
                >
                  {severityLabel(entry.severity)} ({entry.severity.toFixed(2)})
                </span>
                {entry.target_paths.map((p) => (
                  <span
                    key={p}
                    className="rounded border border-border bg-bg-3 px-1.5 py-0.5 font-mono text-[10px]"
                  >
                    {p}
                  </span>
                ))}
              </div>
              <p className="mt-1 whitespace-pre-wrap text-[11px]">{entry.message}</p>
              {Object.keys(entry.by_field).length > 0 && (
                <button
                  type="button"
                  className="mt-1 text-[10px] text-accent underline"
                  onClick={() => toggleExpand(i)}
                >
                  {expanded.has(i) ? "hide" : "show"} per-field breakdown
                </button>
              )}
              {expanded.has(i) && (
                <div className="mt-1 flex flex-col gap-1">
                  {Object.entries(entry.by_field).map(([field, critique]) => (
                    <div key={field}>
                      <div className="font-mono text-[10px] text-muted">{field}</div>
                      <div className="whitespace-pre-wrap text-[11px]">{critique}</div>
                    </div>
                  ))}
                  {entry.applied_diff && (
                    <div>
                      <div className="font-mono text-[10px] text-muted">applied diff</div>
                      <pre className="overflow-auto whitespace-pre-wrap text-[11px]">
                        {entry.applied_diff}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
