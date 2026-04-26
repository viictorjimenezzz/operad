import { Chip } from "@/components/ui/chip";
import { EmptyState } from "@/components/ui/empty-state";
import { SearchInput } from "@/components/ui/search-input";
import { useRunsFiltered } from "@/hooks/use-runs";
import type { RunSummary } from "@/lib/types";
import { useUIStore } from "@/stores";
import { type RunStatusFilter, type RunTimeFilter, useRunsFilterStore } from "@/stores/runs-filter";
import { Archive, ChevronLeft, ChevronRight } from "lucide-react";
import {
  type MouseEvent as ReactMouseEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { RunGroupSection } from "./run-group-section";
import { RunRow } from "./run-row";

const TIME_CUTOFFS: Record<RunTimeFilter, number | null> = {
  all: null,
  "1h": 3600,
  "24h": 86400,
  "7d": 604800,
};

function labelForGroup(group: string): string {
  return group === "__agents__" ? "agents" : group;
}

function groupGlyph(group: string): string {
  const label = labelForGroup(group);
  return label[0]?.toUpperCase() ?? "?";
}

export function RunListSidebar() {
  const { runId: activeRunId } = useParams();
  const navigate = useNavigate();
  const sidebarCollapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);

  const {
    search,
    statusFilter,
    timeFilter,
    showSynthetic,
    setSearch,
    setStatusFilter,
    setTimeFilter,
    setShowSynthetic,
  } = useRunsFilterStore();

  const { data: runs, isLoading } = useRunsFiltered(showSynthetic);

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [lastClickedId, setLastClickedId] = useState<string | null>(null);
  const [openGroup, setOpenGroup] = useState<string | null>(null);
  const toggleButtonRef = useRef<HTMLButtonElement>(null);
  const railPopoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.key !== "\\") return;
      event.preventDefault();
      toggleSidebar();
      queueMicrotask(() => toggleButtonRef.current?.focus());
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [toggleSidebar]);

  useEffect(() => {
    if (!sidebarCollapsed) {
      setOpenGroup(null);
      return;
    }
    const onPointerDown = (event: MouseEvent) => {
      if (!railPopoverRef.current) return;
      if (event.target instanceof Node && railPopoverRef.current.contains(event.target)) return;
      setOpenGroup(null);
    };
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpenGroup(null);
    };
    window.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onEscape);
    return () => {
      window.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onEscape);
    };
  }, [sidebarCollapsed]);

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

  const orderedRunIds = useMemo(
    () => grouped.flatMap(([, gruns]) => gruns.map((r) => r.run_id)),
    [grouped],
  );

  const handleCheck = useCallback(
    (runId: string, e: ReactMouseEvent) => {
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

  const groupForPopover = openGroup ? grouped.find(([label]) => label === openGroup) : undefined;

  return (
    <aside
      className="relative flex h-full flex-col border-r border-border bg-bg-1"
      style={{
        transition: "width 200ms ease",
      }}
    >
      <div className="border-b border-border px-2 py-2">
        <div className="mb-1.5 flex items-center justify-between gap-1">
          {!sidebarCollapsed ? (
            <h2 className="m-0 text-[0.68rem] uppercase tracking-[0.1em] text-muted">runs</h2>
          ) : null}
          <div className="ml-auto flex items-center gap-1">
            {!sidebarCollapsed ? (
              <Link
                to="/archive"
                className="text-[10px] uppercase tracking-[0.08em] text-muted hover:text-text"
              >
                archive
              </Link>
            ) : (
              <Link
                to="/archive"
                aria-label="Open archive"
                className="rounded border border-border bg-bg-2 p-1 text-muted hover:text-text"
              >
                <Archive size={12} />
              </Link>
            )}
            <button
              ref={toggleButtonRef}
              type="button"
              onClick={toggleSidebar}
              aria-label={sidebarCollapsed ? "Expand runs sidebar" : "Collapse runs sidebar"}
              aria-expanded={!sidebarCollapsed}
              className="rounded border border-border bg-bg-2 p-1 text-muted hover:text-text"
              title="Toggle sidebar (cmd+\\)"
            >
              {sidebarCollapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
            </button>
          </div>
        </div>
        {!sidebarCollapsed ? (
          <SearchInput value={search} onChange={setSearch} placeholder="search id, class, path…" />
        ) : null}
      </div>

      {!sidebarCollapsed ? (
        <>
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

          <div className="flex-1 overflow-auto">
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
            {grouped.map(([label, gruns]) => (
              <RunGroupSection
                key={label}
                label={label}
                runs={gruns}
                selectedIds={selectedIds}
                onCheck={handleCheck}
                activeRunId={activeRunId}
              />
            ))}
          </div>
        </>
      ) : (
        <div className="flex-1 overflow-auto px-1 py-2">
          <div className="flex flex-col items-center gap-2">
            {grouped.map(([label, gruns]) => {
              const liveCount = gruns.filter((run) => run.state === "running").length;
              const isOpen = openGroup === label;
              return (
                <button
                  key={label}
                  type="button"
                  className={`relative flex h-9 w-9 items-center justify-center rounded-md border text-[11px] font-semibold transition-all ${
                    isOpen
                      ? "border-accent bg-accent/15 text-text"
                      : "border-border bg-bg-2 text-muted hover:text-text"
                  }`}
                  onClick={() => setOpenGroup((current) => (current === label ? null : label))}
                  aria-label={`Open ${labelForGroup(label)} runs`}
                  title={`${labelForGroup(label)} (${gruns.length})`}
                >
                  {groupGlyph(label)}
                  {liveCount > 0 ? (
                    <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-[--color-ok] shadow-[0_0_6px_var(--color-ok)]" />
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {sidebarCollapsed && groupForPopover ? (
        <div
          ref={railPopoverRef}
          className="absolute left-[calc(100%+8px)] top-2 z-20 w-[320px] overflow-hidden rounded-md border border-border bg-bg-1 shadow-xl"
        >
          <div className="border-b border-border px-3 py-2 text-[11px] uppercase tracking-[0.1em] text-muted">
            {labelForGroup(groupForPopover[0])}
          </div>
          <div className="max-h-[60vh] overflow-auto">
            <ul>
              {groupForPopover[1].map((run) => (
                <RunRow
                  key={run.run_id}
                  run={run}
                  active={run.run_id === activeRunId}
                  checked={selectedIds.has(run.run_id)}
                  onCheck={(e) => handleCheck(run.run_id, e)}
                />
              ))}
            </ul>
          </div>
        </div>
      ) : null}

      {selectedIds.size >= 2 && (
        <div className="flex items-center justify-between border-t border-border bg-bg-2 px-2 py-2">
          {!sidebarCollapsed ? (
            <span className="text-xs text-muted">{selectedIds.size} selected</span>
          ) : null}
          <button
            type="button"
            onClick={() => navigate(`/experiments?runs=${[...selectedIds].join(",")}`)}
            className="ml-auto rounded border border-accent bg-accent-dim px-2 py-1 text-xs text-text hover:bg-accent/20"
          >
            {sidebarCollapsed ? "cmp" : "Compare"}
          </button>
        </div>
      )}
    </aside>
  );
}
