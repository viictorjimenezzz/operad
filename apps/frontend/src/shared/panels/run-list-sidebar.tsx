import { useRunsFiltered } from "@/hooks/use-runs";
import type { RunSummary } from "@/lib/types";
import { Chip } from "@/shared/ui/chip";
import { EmptyState } from "@/shared/ui/empty-state";
import { SearchInput } from "@/shared/ui/search-input";
import { useRunsFilterStore, type RunStatusFilter, type RunTimeFilter } from "@/stores/runs-filter";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useCallback, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { RunGroupSection } from "./run-group-section";

const TIME_CUTOFFS: Record<RunTimeFilter, number | null> = {
  all: null,
  "1h": 3600,
  "24h": 86400,
  "7d": 604800,
};

type VirtualItem =
  | { type: "group"; label: string; runs: RunSummary[] }
  | { type: "run"; run: RunSummary; groupLabel: string };

function GroupHeader({ label, count }: { label: string; count: number }) {
  return (
    <details open className="group">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 border-b border-border bg-bg-1 px-2 py-1 text-[0.68rem] uppercase tracking-[0.1em] text-muted hover:text-text">
        <span className="flex-1">{label === "__agents__" ? "agents" : label}</span>
        <span className="rounded-full bg-bg-3 px-1.5 py-0.5 text-[9px] tabular-nums text-muted-2">
          {count}
        </span>
      </summary>
    </details>
  );
}

export function RunListSidebar() {
  const { runId: activeRunId } = useParams();
  const navigate = useNavigate();

  const { search, statusFilter, timeFilter, showSynthetic, setSearch, setStatusFilter, setTimeFilter, setShowSynthetic } =
    useRunsFilterStore();

  const { data: runs, isLoading } = useRunsFiltered(showSynthetic);

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [lastClickedId, setLastClickedId] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const nowSecs = Date.now() / 1000;
    const cutoff = TIME_CUTOFFS[timeFilter];
    const q = search.trim().toLowerCase();

    return (runs ?? []).filter((r) => {
      if (r.synthetic && !showSynthetic) return false;
      if (cutoff !== null && r.started_at < nowSecs - cutoff) return false;
      if (statusFilter === "running" && r.state !== "running") return false;
      if (statusFilter === "ended" && r.state !== "ended") return false;
      if (statusFilter === "errors" && r.state !== "error") return false;
      if (q) {
        const haystack = [r.run_id, r.algorithm_class ?? "", r.algorithm_path ?? ""]
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [runs, showSynthetic, timeFilter, statusFilter, search]);

  const grouped = useMemo(() => {
    const map = new Map<string, RunSummary[]>();
    for (const run of filtered) {
      const key = run.algorithm_class ?? "__agents__";
      const arr = map.get(key);
      if (arr) arr.push(run);
      else map.set(key, [run]);
    }
    return [...map.entries()].sort(([a], [b]) => {
      if (a === "__agents__") return 1;
      if (b === "__agents__") return -1;
      return a.localeCompare(b);
    });
  }, [filtered]);

  // Flat list of all run IDs in current render order (for range select)
  const orderedRunIds = useMemo(() => grouped.flatMap(([, runs]) => runs.map((r) => r.run_id)), [grouped]);

  const handleCheck = useCallback(
    (runId: string, e: React.MouseEvent) => {
      const isShift = e.shiftKey;
      const isCmd = e.metaKey || e.ctrlKey;

      if (isShift && lastClickedId) {
        const a = orderedRunIds.indexOf(lastClickedId);
        const b = orderedRunIds.indexOf(runId);
        const range = orderedRunIds.slice(Math.min(a, b), Math.max(a, b) + 1);
        setSelectedIds((prev) => new Set([...prev, ...range]));
      } else if (isCmd) {
        setSelectedIds((prev) => {
          const next = new Set(prev);
          if (next.has(runId)) next.delete(runId);
          else next.add(runId);
          return next;
        });
      } else {
        setSelectedIds((prev) => {
          const next = new Set<string>();
          if (!prev.has(runId)) next.add(runId);
          return next;
        });
      }
      setLastClickedId(runId);
    },
    [orderedRunIds, lastClickedId],
  );

  // Build virtual items: one header per group + one row per run
  const virtualItems = useMemo<VirtualItem[]>(() => {
    const items: VirtualItem[] = [];
    for (const [label, runs] of grouped) {
      items.push({ type: "group", label, runs });
      for (const run of runs) {
        items.push({ type: "run", run, groupLabel: label });
      }
    }
    return items;
  }, [grouped]);

  const scrollRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: virtualItems.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: (i) => (virtualItems[i]?.type === "group" ? 28 : 44),
    overscan: 8,
  });

  return (
    <aside className="flex h-full flex-col border-r border-border bg-bg-1">
      <div className="border-b border-border px-2 py-2">
        <h2 className="m-0 mb-1.5 text-[0.68rem] uppercase tracking-[0.1em] text-muted">runs</h2>
        <SearchInput value={search} onChange={setSearch} placeholder="search id, class, path…" />
      </div>

      <div className="border-b border-border px-2 py-1.5">
        <div className="mb-1 flex flex-wrap gap-1">
          {(["all", "1h", "24h", "7d"] as RunTimeFilter[]).map((t) => (
            <Chip key={t} active={timeFilter === t} onClick={() => setTimeFilter(t)}>
              {t}
            </Chip>
          ))}
        </div>
        <div className="flex flex-wrap gap-1">
          {(["all", "running", "ended", "errors"] as RunStatusFilter[]).map((s) => (
            <Chip key={s} active={statusFilter === s} onClick={() => setStatusFilter(s)}>
              {s}
            </Chip>
          ))}
          <Chip active={showSynthetic} onClick={() => setShowSynthetic(!showSynthetic)}>
            inner
          </Chip>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-auto">
        {isLoading && <div className="p-3 text-xs text-muted">loading…</div>}
        {!isLoading && filtered.length === 0 && (
          <EmptyState
            title="no runs yet"
            description={
              <>
                run a demo:
                <br />
                <code className="mt-1 block rounded bg-bg-2 px-1.5 py-1 font-mono text-[10px]">
                  uv run python apps/demos/agent_evolution/run.py --offline --dashboard
                </code>
              </>
            }
          />
        )}
        {virtualItems.length > 0 && (
          <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
            {virtualizer.getVirtualItems().map((vItem) => {
              const item = virtualItems[vItem.index];
              if (!item) return null;
              return (
                <div
                  key={vItem.key}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    transform: `translateY(${vItem.start}px)`,
                  }}
                >
                  {item.type === "group" ? (
                    <GroupHeader label={item.label} count={item.runs.length} />
                  ) : (
                    <RunGroupSection
                      label={item.groupLabel}
                      runs={[item.run]}
                      selectedIds={selectedIds}
                      onCheck={handleCheck}
                      activeRunId={activeRunId}
                    />
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {selectedIds.size >= 2 && (
        <div className="flex items-center justify-between border-t border-border bg-bg-2 px-3 py-2">
          <span className="text-xs text-muted">{selectedIds.size} selected</span>
          <button
            type="button"
            onClick={() => navigate(`/experiments?runs=${[...selectedIds].join(",")}`)}
            className="rounded border border-accent bg-accent-dim px-2.5 py-1 text-xs text-text hover:bg-accent/20"
          >
            Compare
          </button>
        </div>
      )}
    </aside>
  );
}
