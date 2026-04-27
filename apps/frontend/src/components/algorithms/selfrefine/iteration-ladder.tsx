import { EmptyState } from "@/components/ui/empty-state";
import { MarkdownView } from "@/components/ui/markdown";
import { useUrlState } from "@/hooks/use-url-state";
import { IterationsResponse, RunSummary as RunSummarySchema } from "@/lib/types";
import type { RunSummary } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useEffect, useMemo, useState } from "react";
import { z } from "zod";

type IterationEntry = IterationsResponse["iterations"][number];

interface LadderItem {
  iterIndex: number;
  draftText: string | null;
  reflection: IterationEntry | null;
  score: number | null;
  previousScore: number | null;
}

export function IterationLadder({
  data,
  dataChildren,
}: {
  data: unknown;
  dataChildren?: unknown;
}) {
  const parsed = IterationsResponse.safeParse(data);
  const children = parseChildren(dataChildren);
  const [iterParam, setIterParam] = useUrlState("iter");
  const pinnedIter = parseNonNegativeInt(iterParam);
  const items = useMemo(() => (parsed.success ? buildItems(parsed.data.iterations) : []), [parsed]);
  const [open, setOpen] = useState<Record<number, boolean>>({});
  const [activeIter, setActiveIter] = useState<number | null>(pinnedIter);
  const threshold = parsed.success ? parsed.data.threshold : null;

  useEffect(() => {
    if (pinnedIter != null) {
      setActiveIter(pinnedIter);
      setOpen((current) => ({ ...current, [pinnedIter]: true }));
    }
  }, [pinnedIter]);

  if (!parsed.success || items.length === 0) {
    return (
      <EmptyState
        title="no refinement iterations"
        description="iteration events have not arrived yet"
      />
    );
  }

  const activeChildren = activeIter == null ? [] : childrenForIter(children, activeIter);

  return (
    <div className="grid h-full gap-4 overflow-auto p-4 xl:grid-cols-[minmax(0,1fr)_320px]">
      <ol className="relative flex flex-col gap-4 border-l border-border pl-5">
        {threshold != null ? (
          <div className="absolute left-0 top-0 -translate-x-1/2 rounded-full border border-[var(--color-ok)] bg-bg px-1.5 py-0.5 text-[10px] text-[var(--color-ok)]">
            threshold {threshold.toFixed(2)}
          </div>
        ) : null}
        {items.map((item, index) => {
          const defaultOpen = index < 3;
          const isOpen = open[item.iterIndex] ?? defaultOpen;
          return (
            <li key={item.iterIndex}>
              <IterationCard
                item={item}
                threshold={threshold}
                open={isOpen}
                active={activeIter === item.iterIndex}
                onToggle={() => {
                  setOpen((current) => ({ ...current, [item.iterIndex]: !isOpen }));
                  setActiveIter(item.iterIndex);
                  setIterParam(String(item.iterIndex));
                }}
              />
            </li>
          );
        })}
      </ol>

      <aside className="rounded-lg border border-border bg-bg-1 p-3">
        <div className="mb-2 text-[12px] font-medium text-text">
          Iteration {activeIter ?? items[0]?.iterIndex ?? 0} child runs
        </div>
        {activeChildren.length > 0 ? (
          <div className="flex flex-col gap-2">
            {activeChildren.map((child) => (
              <a
                key={child.run_id}
                className="rounded border border-border bg-bg-2 px-2 py-1.5 text-[11px] text-text transition-colors hover:border-border-strong"
                href={childHref(child)}
              >
                <span className="block font-mono">{child.root_agent_path ?? child.run_id}</span>
                <span className="text-muted">{child.state}</span>
              </a>
            ))}
          </div>
        ) : (
          <EmptyState
            title="no child links"
            description="synthetic children for this iteration are not available"
            className="min-h-40"
          />
        )}
      </aside>
    </div>
  );
}

function IterationCard({
  item,
  threshold,
  open,
  active,
  onToggle,
}: {
  item: LadderItem;
  threshold: number | null;
  open: boolean;
  active: boolean;
  onToggle: () => void;
}) {
  const delta =
    item.score != null && item.previousScore != null ? item.score - item.previousScore : null;
  const crossed = threshold != null && item.score != null && item.score >= threshold;
  const needsRevision = item.reflection?.metadata.needs_revision;
  const critique = item.reflection?.metadata.critique_summary;

  return (
    <section
      className={cn(
        "relative rounded-lg border bg-bg-1",
        active ? "border-accent" : "border-border",
        crossed && "shadow-[inset_3px_0_0_var(--color-ok)]",
      )}
    >
      <span className="absolute -left-[27px] top-3 h-3 w-3 rounded-full border border-border bg-bg-1" />
      <button
        type="button"
        className="flex w-full items-start justify-between gap-3 border-b border-border px-3 py-2 text-left transition-colors hover:bg-bg-2"
        onClick={onToggle}
      >
        <div>
          <div className="text-[12px] font-medium text-text">Iteration {item.iterIndex}</div>
          <div className="mt-0.5 flex flex-wrap gap-2 text-[11px] text-muted">
            <span>
              score {formatScore(item.previousScore)} → {formatScore(item.score)}
            </span>
            {delta != null ? (
              <span className={delta >= 0 ? "text-[var(--color-ok)]" : "text-[var(--color-err)]"}>
                {delta >= 0 ? "+" : ""}
                {delta.toFixed(2)}
              </span>
            ) : null}
            {crossed ? <span className="text-[var(--color-ok)]">converged here</span> : null}
          </div>
        </div>
        <span className="text-[11px] text-muted">{open ? "collapse" : "expand"}</span>
      </button>

      {open ? (
        <div className="flex flex-col gap-3 p-3">
          <div>
            <div className="mb-1 text-[11px] font-medium uppercase tracking-[0.08em] text-muted">
              {item.iterIndex === 0 ? "Generate" : "Refine"}
            </div>
            <MarkdownView value={item.draftText ?? "No draft text recorded."} />
          </div>
          <div className="rounded border border-border bg-bg-2 p-3">
            <div className="mb-1 flex items-center justify-between gap-2">
              <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-muted">
                Reflect
              </div>
              <div className="font-mono text-[11px] text-text">{formatScore(item.score)}</div>
            </div>
            <blockquote className="m-0 border-l-2 border-border pl-3 text-[12px] leading-5 text-text/80">
              {typeof critique === "string" && critique.length > 0
                ? critique
                : "No critique summary recorded."}
            </blockquote>
            {needsRevision != null ? (
              <div className="mt-2 text-[11px] text-muted">
                needs revision: <span className="text-text">{String(needsRevision)}</span>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function buildItems(entries: IterationEntry[]): LadderItem[] {
  const byIter = new Map<number, IterationEntry[]>();
  for (const entry of entries) {
    const bucket = byIter.get(entry.iter_index) ?? [];
    bucket.push(entry);
    byIter.set(entry.iter_index, bucket);
  }

  const items = [...byIter.entries()]
    .sort(([a], [b]) => a - b)
    .map(([iterIndex, bucket]) => {
      const reflect = bucket.find((entry) => entry.phase === "reflect") ?? null;
      const refine = bucket.find((entry) => entry.phase === "refine") ?? null;
      const draftText = refine?.text ?? reflect?.text ?? null;
      return {
        iterIndex,
        draftText,
        reflection: reflect,
        score: reflect?.score ?? null,
        previousScore: null,
      };
    });

  let previousScore: number | null = null;
  return items.map((item) => {
    const withPrevious = { ...item, previousScore };
    if (item.score != null) previousScore = item.score;
    return withPrevious;
  });
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

function childrenForIter(children: RunSummary[], iterIndex: number): RunSummary[] {
  const start = iterIndex === 0 ? 0 : iterIndex * 2;
  return children.slice(start, start + 2);
}

function childHref(child: RunSummary): string {
  const identity = child.root_agent_path ?? child.run_id;
  return `/agents/${encodeURIComponent(identity)}/runs/${encodeURIComponent(child.run_id)}`;
}

function parseNonNegativeInt(value: string | null): number | null {
  if (value == null) return null;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function formatScore(value: number | null | undefined): string {
  return typeof value === "number" ? value.toFixed(2) : "n/a";
}
