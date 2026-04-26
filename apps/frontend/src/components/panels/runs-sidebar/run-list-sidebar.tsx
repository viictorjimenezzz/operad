import { SidebarFilterPopover } from "@/components/panels/runs-sidebar/sidebar-filter-popover";
import { SidebarSearchPopover } from "@/components/panels/runs-sidebar/sidebar-search-popover";
import { Button, EmptyState, IconButton } from "@/components/ui";
import { useRunsFiltered } from "@/hooks/use-runs";
import type { RunSummary } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores";
import { type RunTimeFilter, useRunsFilterStore } from "@/stores/runs-filter";
import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  type MouseEvent as ReactMouseEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useNavigate, useParams } from "react-router-dom";
import { RunGroupSection } from "./run-group-section";
import { RunRow } from "./run-row";

const TIME_CUTOFFS: Record<RunTimeFilter, number | null> = {
  all: null,
  "1h": 3600,
  "24h": 86400,
  "7d": 604800,
};

function labelForGroup(group: string): string {
  return group === "__agents__" ? "Agents" : group;
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

  const { search, statusFilter, timeFilter, showSynthetic, setSearch } = useRunsFilterStore();

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

  const handleSelect = useCallback(
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
      }
      setLastClickedId(runId);
    },
    [orderedRunIds, lastClickedId],
  );

  const groupForPopover = openGroup ? grouped.find(([label]) => label === openGroup) : undefined;

  return (
    <aside
      className="relative flex h-full flex-col border-r border-border bg-bg-1"
      style={{ transition: "width 200ms ease" }}
    >
      <div className="flex items-center gap-1.5 border-b border-border px-2 py-2">
        {!sidebarCollapsed ? (
          <>
            <SidebarSearchPopover value={search} onChange={setSearch} />
            <SidebarFilterPopover />
            <span className="ml-auto" />
          </>
        ) : (
          <span className="ml-auto" />
        )}
        <IconButton
          ref={toggleButtonRef}
          aria-label={sidebarCollapsed ? "expand runs sidebar" : "collapse runs sidebar"}
          aria-expanded={!sidebarCollapsed}
          onClick={toggleSidebar}
          title="toggle (cmd+\\)"
          size="sm"
        >
          {sidebarCollapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
        </IconButton>
      </div>

      {!sidebarCollapsed ? (
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
              onSelect={handleSelect}
              activeRunId={activeRunId ?? null}
            />
          ))}
        </div>
      ) : (
        <div className="flex-1 overflow-auto px-1.5 py-2">
          <div className="flex flex-col items-center gap-1.5">
            {grouped.map(([label, gruns]) => {
              const liveCount = gruns.filter((run) => run.state === "running").length;
              const isOpen = openGroup === label;
              return (
                <button
                  key={label}
                  type="button"
                  className={cn(
                    "relative flex h-9 w-9 items-center justify-center rounded-lg border text-[12px] font-medium transition-colors",
                    isOpen
                      ? "border-border-strong bg-bg-3 text-text"
                      : "border-transparent text-muted hover:bg-bg-3 hover:text-text",
                  )}
                  onClick={() => setOpenGroup((current) => (current === label ? null : label))}
                  aria-label={`Open ${labelForGroup(label)} runs`}
                  title={`${labelForGroup(label)} (${gruns.length})`}
                >
                  {groupGlyph(label)}
                  {liveCount > 0 ? (
                    <span className="absolute right-0.5 top-0.5 h-1.5 w-1.5 rounded-full bg-[--color-ok] shadow-[0_0_6px_var(--color-ok)]" />
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
          className="absolute left-[calc(100%+8px)] top-2 z-20 w-[320px] overflow-hidden rounded-xl border border-border-strong bg-bg-1 shadow-[var(--shadow-popover)]"
        >
          <div className="border-b border-border px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-muted">
            {labelForGroup(groupForPopover[0])}
          </div>
          <div className="max-h-[60vh] overflow-auto">
            <ul>
              {groupForPopover[1].map((run) => (
                <RunRow
                  key={run.run_id}
                  run={run}
                  active={run.run_id === activeRunId}
                  selected={selectedIds.has(run.run_id)}
                  onSelect={(e) => handleSelect(run.run_id, e)}
                />
              ))}
            </ul>
          </div>
        </div>
      ) : null}

      {selectedIds.size >= 2 && (
        <div className="flex items-center justify-between border-t border-border bg-bg-1 px-2 py-2">
          {!sidebarCollapsed ? (
            <span className="text-[12px] text-muted">{selectedIds.size} selected</span>
          ) : null}
          <Button
            size="sm"
            variant="primary"
            className="ml-auto"
            onClick={() => navigate(`/experiments?runs=${[...selectedIds].join(",")}`)}
          >
            {sidebarCollapsed ? "cmp" : "Compare"}
          </Button>
        </div>
      )}
    </aside>
  );
}
