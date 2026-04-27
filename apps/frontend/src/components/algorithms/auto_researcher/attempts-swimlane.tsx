import { EmptyState } from "@/components/ui/empty-state";
import { useUrlState } from "@/hooks/use-url-state";
import { IterationsResponse, RunSummary as RunSummarySchema } from "@/lib/types";
import type { RunSummary } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useEffect, useMemo, useState } from "react";
import { z } from "zod";

type IterationEntry = IterationsResponse["iterations"][number];

interface AttemptRow {
  entry: IterationEntry;
  attemptIndex: number | null;
  child: RunSummary | null;
}

interface AttemptGroup {
  attemptIndex: number | null;
  rows: AttemptRow[];
  bestScore: number | null;
}

export function AttemptsSwimlane({
  data,
  dataChildren,
}: {
  data: unknown;
  dataChildren?: unknown;
}) {
  const parsed = IterationsResponse.safeParse(data);
  const children = parseChildren(dataChildren);
  const [attemptParam, setAttemptParam] = useUrlState("attempt");
  const pinnedAttempt = parseNonNegativeInt(attemptParam);
  const groups = useMemo(
    () => (parsed.success ? buildGroups(parsed.data.iterations, children) : []),
    [parsed, children],
  );
  const hasAttemptIndex = groups.some((group) => group.attemptIndex != null);
  const [activeAttempt, setActiveAttempt] = useState<number | null>(pinnedAttempt);

  useEffect(() => {
    if (pinnedAttempt != null) setActiveAttempt(pinnedAttempt);
  }, [pinnedAttempt]);

  if (!parsed.success || parsed.data.iterations.length === 0) {
    return (
      <EmptyState
        title="no attempt events"
        description="AutoResearcher iteration events have not arrived yet"
      />
    );
  }

  const visibleGroups =
    activeAttempt == null
      ? groups
      : groups.filter(
          (group) => group.attemptIndex === activeAttempt || group.attemptIndex == null,
        );

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-4">
      {!hasAttemptIndex ? (
        <EmptyState
          title="attempt index missing"
          description="legacy AutoResearcher runs are grouped under attempt unknown; new runs emit attempt_index on every iteration"
          className="min-h-28 rounded-lg border border-border bg-bg-1"
        />
      ) : (
        <div className="sticky top-0 z-10 -mx-4 -mt-4 border-b border-border bg-bg/95 px-4 py-3 backdrop-blur">
          <div className="mb-2 flex items-center justify-between gap-3">
            <div className="text-[12px] font-medium text-text">Pinned attempt</div>
            <div className="font-mono text-[11px] text-muted">
              {activeAttempt == null ? "all" : `?attempt=${activeAttempt}`}
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              className={pinClass(activeAttempt == null)}
              onClick={() => {
                setActiveAttempt(null);
                setAttemptParam(null);
              }}
            >
              All
            </button>
            {groups
              .filter((group) => group.attemptIndex != null)
              .map((group) => (
                <button
                  key={group.attemptIndex}
                  type="button"
                  className={pinClass(activeAttempt === group.attemptIndex)}
                  onClick={() => {
                    setActiveAttempt(group.attemptIndex);
                    setAttemptParam(String(group.attemptIndex));
                  }}
                >
                  Attempt {(group.attemptIndex ?? 0) + 1}
                </button>
              ))}
          </div>
        </div>
      )}

      {visibleGroups.map((group) => (
        <section
          key={group.attemptIndex ?? "unknown"}
          className="rounded-lg border border-border bg-bg-1"
        >
          <div className="flex items-center justify-between gap-3 border-b border-border px-3 py-2">
            <div>
              <div className="text-[12px] font-medium text-text">
                {group.attemptIndex == null
                  ? "Attempt unknown"
                  : `Attempt #${group.attemptIndex + 1}`}
              </div>
              <div className="text-[11px] text-muted">
                {group.rows.length} events · best score {formatScore(group.bestScore)}
              </div>
            </div>
            {group.bestScore != null ? (
              <span className="rounded bg-[var(--color-ok)]/15 px-1.5 py-0.5 font-mono text-[11px] text-[var(--color-ok)]">
                {group.bestScore.toFixed(2)}
              </span>
            ) : null}
          </div>
          <ol className="flex flex-col divide-y divide-border">
            {group.rows.map((row, index) => (
              <li
                key={`${row.entry.iter_index}-${row.entry.phase}-${index}`}
                className="flex items-center gap-3 px-3 py-2 text-[12px]"
              >
                <span className="w-14 font-mono text-muted">iter {row.entry.iter_index}</span>
                <span
                  className={cn(
                    "w-20 rounded px-1.5 py-0.5 text-center text-[11px]",
                    row.entry.phase === "reflect"
                      ? "bg-[var(--color-warn)]/15 text-[var(--color-warn)]"
                      : "bg-accent/10 text-accent",
                  )}
                >
                  {row.entry.phase ?? "event"}
                </span>
                <span className="w-20 font-mono tabular-nums text-text">
                  {formatScore(row.entry.score)}
                </span>
                <span className="min-w-0 flex-1 truncate text-muted">
                  {row.entry.metadata.needs_revision != null
                    ? `needs_revision = ${String(row.entry.metadata.needs_revision)}`
                    : row.entry.score != null
                      ? "score recorded"
                      : "no score"}
                </span>
                {row.child ? (
                  <a
                    className="rounded border border-border px-2 py-1 text-[11px] text-text transition-colors hover:border-border-strong hover:bg-bg-2"
                    href={childHref(row.child)}
                  >
                    Open run
                  </a>
                ) : null}
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}

function buildGroups(entries: IterationEntry[], children: RunSummary[]): AttemptGroup[] {
  let childIndex = 0;
  const rows = entries.map((entry) => {
    const attemptIndex =
      typeof entry.metadata.attempt_index === "number" ? entry.metadata.attempt_index : null;
    const child = children[childIndex] ?? null;
    childIndex += entry.phase === "reflect" ? 0 : 1;
    return { entry, attemptIndex, child };
  });

  const grouped = new Map<string, AttemptRow[]>();
  for (const row of rows) {
    const key = row.attemptIndex == null ? "unknown" : String(row.attemptIndex);
    grouped.set(key, [...(grouped.get(key) ?? []), row]);
  }

  return [...grouped.entries()]
    .map(([key, groupRows]) => {
      const attemptIndex = key === "unknown" ? null : Number(key);
      const scores = groupRows
        .map((row) => row.entry.score)
        .filter((score): score is number => typeof score === "number");
      return {
        attemptIndex,
        rows: groupRows,
        bestScore: scores.length > 0 ? Math.max(...scores) : null,
      };
    })
    .sort(
      (a, b) =>
        (a.attemptIndex ?? Number.MAX_SAFE_INTEGER) - (b.attemptIndex ?? Number.MAX_SAFE_INTEGER),
    );
}

function parseChildren(data: unknown): RunSummary[] {
  const raw = Array.isArray(data)
    ? data
    : data && typeof data === "object" && Array.isArray((data as Record<string, unknown>).children)
      ? (data as Record<string, unknown>).children
      : [];
  const parsed = z.array(RunSummarySchema).safeParse(raw);
  return parsed.success ? parsed.data : [];
}

function childHref(child: RunSummary): string {
  const identity = child.root_agent_path ?? child.run_id;
  return `/agents/${encodeURIComponent(identity)}/runs/${encodeURIComponent(child.run_id)}`;
}

function pinClass(active: boolean): string {
  return cn(
    "rounded border px-2 py-1 text-[11px] transition-colors",
    active
      ? "border-accent bg-accent/10 text-text"
      : "border-border bg-bg-1 text-muted hover:border-border-strong hover:text-text",
  );
}

function parseNonNegativeInt(value: string | null): number | null {
  if (value == null) return null;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function formatScore(value: number | null | undefined): string {
  return typeof value === "number" ? value.toFixed(2) : "n/a";
}
