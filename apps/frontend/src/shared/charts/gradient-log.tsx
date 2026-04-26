import { useState } from "react";
import { GradientEntry } from "@/lib/types";
import { EmptyState } from "@/shared/ui/empty-state";
import { z } from "zod";

const Schema = z.array(GradientEntry);

const severityClass: Record<string, string> = {
  high: "bg-red-900/40 text-red-300 border-red-700",
  medium: "bg-yellow-900/40 text-yellow-300 border-yellow-700",
  low: "bg-blue-900/40 text-blue-300 border-blue-700",
  info: "bg-bg-3 text-muted border-border",
};

function badge(severity: string) {
  return severityClass[severity] ?? severityClass["info"];
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
        e.target_paths.some((p) => p.toLowerCase().includes(q)),
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
                  {entry.severity}
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
                  className="mt-1 text-[10px] text-accent underline"
                  onClick={() => toggleExpand(i)}
                >
                  {expanded.has(i) ? "hide" : "show"} per-field breakdown
                </button>
              )}
              {expanded.has(i) && (
                <dl className="mt-1 flex flex-col gap-1">
                  {Object.entries(entry.by_field).map(([field, critique]) => (
                    <div key={field}>
                      <dt className="font-mono text-[10px] text-muted">{field}</dt>
                      <dd className="whitespace-pre-wrap text-[11px]">{critique}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
