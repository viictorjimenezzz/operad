import { AgentsTree } from "@/components/panels/section-sidebar/agents-tree";
import { AlgorithmsTree } from "@/components/panels/section-sidebar/algorithms-tree";
import { OPROTree } from "@/components/panels/section-sidebar/opro-tree";
import { TrainingTree } from "@/components/panels/section-sidebar/training-tree";
import {
  DEFAULT_SIDEBAR_FILTERS,
  type SidebarFilters,
  type SidebarRail,
} from "@/components/panels/section-sidebar/types";
import { IconButton } from "@/components/ui";
import {
  useAgentGroups,
  useAlgorithmGroups,
  useOPRORuns,
  useTrainingGroups,
} from "@/hooks/use-runs";
import type { AgentGroupSummary, AlgorithmGroup, RunSummary, TrainingGroup } from "@/lib/types";
import { useUIStore } from "@/stores";
import { ChevronLeft, ChevronRight, Search, SlidersHorizontal, X } from "lucide-react";
import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

export function SectionSidebar() {
  const location = useLocation();
  const sidebarCollapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const toggleButtonRef = useRef<HTMLButtonElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const [filters, setFilters] = useState<SidebarFilters>(DEFAULT_SIDEBAR_FILTERS);

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

  const path = location.pathname;
  const rail: SidebarRail = path.startsWith("/algorithms")
    ? "algorithms"
    : path.startsWith("/training")
      ? "training"
      : path.startsWith("/opro")
        ? "opro"
        : "agents";

  useEffect(() => {
    setFilters(DEFAULT_SIDEBAR_FILTERS);
    setFilterOpen(false);
  }, [rail]);

  useEffect(() => {
    if (searchOpen) searchInputRef.current?.focus();
  }, [searchOpen]);

  const stats = useSidebarStats(rail, search, filters);
  const railTitle =
    rail === "algorithms"
      ? "Algorithms"
      : rail === "training"
        ? "Training"
        : rail === "opro"
          ? "OPRO"
          : "Agents";
  const onSearchChange = (e: ChangeEvent<HTMLInputElement>) => setSearch(e.target.value);
  const activeFilters = countActiveFilters(filters, rail);

  return (
    <aside
      className="relative flex h-full flex-col border-r border-border bg-bg-1"
      style={{ transition: "width 200ms ease" }}
    >
      <div className="flex h-10 items-center gap-2 border-b border-border px-2.5">
        {!sidebarCollapsed ? (
          <span className="min-w-0 flex-1 truncate text-[13px] font-semibold text-text">
            {railTitle}
          </span>
        ) : (
          <span className="ml-auto" />
        )}
        <IconButton
          ref={toggleButtonRef}
          aria-label={sidebarCollapsed ? "expand sidebar" : "collapse sidebar"}
          aria-expanded={!sidebarCollapsed}
          onClick={toggleSidebar}
          title="toggle (cmd+\\)"
          size="sm"
        >
          {sidebarCollapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
        </IconButton>
      </div>

      {!sidebarCollapsed ? (
        <>
          <div className="relative flex h-10 items-center gap-2 border-b border-border px-2.5">
            {searchOpen ? (
              <div className="relative flex h-7 min-w-0 flex-1 items-center rounded-md border border-border bg-bg px-2 focus-within:border-border-strong">
                <Search size={12} className="text-muted-2" />
                <input
                  ref={searchInputRef}
                  type="text"
                  value={search}
                  onChange={onSearchChange}
                  onKeyDown={(event) => {
                    if (event.key === "Escape" && search.length === 0) setSearchOpen(false);
                  }}
                  placeholder="Search..."
                  className="ml-1.5 w-full bg-transparent text-[12px] text-text outline-none placeholder:text-muted-2"
                />
                {search ? (
                  <button
                    type="button"
                    aria-label="clear search"
                    onClick={() => setSearch("")}
                    className="rounded p-0.5 text-muted-2 hover:bg-bg-3 hover:text-text"
                  >
                    <X size={12} />
                  </button>
                ) : null}
              </div>
            ) : (
              <div className="min-w-0 flex-1 truncate text-[11px] uppercase tracking-[0.06em] text-muted">
                {stats.countLabel}
              </div>
            )}
            {!searchOpen ? (
              <IconButton
                aria-label="open search"
                onClick={() => setSearchOpen(true)}
                title="search"
                size="sm"
              >
                <Search size={13} />
              </IconButton>
            ) : null}
            <IconButton
              aria-label="open filters"
              active={filterOpen || activeFilters > 0}
              onClick={() => setFilterOpen((value) => !value)}
              title="filters"
              size="sm"
            >
              <SlidersHorizontal size={13} />
            </IconButton>
            {filterOpen ? (
              <FilterPopover
                rail={rail}
                filters={filters}
                options={stats.options}
                onChange={(key, value) =>
                  setFilters((current) => ({ ...current, [key]: value }))
                }
                onClear={() => setFilters(DEFAULT_SIDEBAR_FILTERS)}
              />
            ) : null}
          </div>
          <div className="flex-1 overflow-auto">
            {rail === "agents" ? <AgentsTree search={search} filters={filters} /> : null}
            {rail === "algorithms" ? <AlgorithmsTree search={search} filters={filters} /> : null}
            {rail === "training" ? <TrainingTree search={search} filters={filters} /> : null}
            {rail === "opro" ? <OPROTree search={search} filters={filters} /> : null}
          </div>
        </>
      ) : (
        <div className="flex-1 overflow-auto px-1.5 py-2" />
      )}
    </aside>
  );
}

type FilterOptions = {
  classes: string[];
  backends: string[];
  models: string[];
  scripts: string[];
  algorithms: string[];
  trainees: string[];
};

function useSidebarStats(rail: SidebarRail, search: string, filters: SidebarFilters) {
  const agents = useAgentGroups();
  const algorithms = useAlgorithmGroups();
  const training = useTrainingGroups();
  const opro = useOPRORuns();
  return useMemo(() => {
    if (rail === "agents") return agentStats(agents.data ?? [], search, filters);
    if (rail === "training") return trainingStats(training.data ?? [], search, filters);
    if (rail === "opro") return algorithmStats(opro.data ?? [], search, filters, "run");
    return algorithmStats(algorithms.data ?? [], search, filters, "run");
  }, [rail, agents.data, algorithms.data, training.data, opro.data, search, filters]);
}

function agentStats(groups: AgentGroupSummary[], search: string, filters: SidebarFilters) {
  const filtered = filterAgents(groups, search, filters);
  return {
    countLabel: `${filtered.length} instance${filtered.length === 1 ? "" : "s"}`,
    options: {
      classes: unique(groups.map((g) => g.class_name)),
      backends: unique(groups.flatMap((g) => g.backends)),
      models: unique(groups.flatMap((g) => g.models)),
      scripts: [],
      algorithms: [],
      trainees: [],
    },
  };
}

function algorithmStats(
  groups: AlgorithmGroup[],
  search: string,
  filters: SidebarFilters,
  label: string,
) {
  const runs = filterAlgorithmRuns(groups, search, filters);
  return {
    countLabel: `${runs.length} ${label}${runs.length === 1 ? "" : "s"}`,
    options: {
      classes: unique(groups.map((g) => g.class_name)),
      backends: [],
      models: [],
      scripts: unique(groups.flatMap((g) => g.runs.map((run) => run.script))),
      algorithms: unique(groups.map((g) => g.class_name ?? g.algorithm_path)),
      trainees: [],
    },
  };
}

function trainingStats(groups: TrainingGroup[], search: string, filters: SidebarFilters) {
  const runs = filterTrainingGroups(groups, search, filters).flatMap((group) => group.runs);
  return {
    countLabel: `${runs.length} training run${runs.length === 1 ? "" : "s"}`,
    options: {
      classes: [],
      backends: [],
      models: [],
      scripts: [],
      algorithms: unique(groups.map((g) => g.algorithm_path)),
      trainees: unique(groups.map((g) => g.class_name ?? g.root_agent_path)),
    },
  };
}

export function filterAgents(
  groups: AgentGroupSummary[],
  search: string,
  filters: SidebarFilters,
): AgentGroupSummary[] {
  const q = search.trim().toLowerCase();
  return groups
    .filter((g) => withinTime(g.last_seen, filters.timeRange))
    .filter((g) => filters.state === "all" || groupState(g) === filters.state)
    .filter((g) => filters.className === "all" || g.class_name === filters.className)
    .filter((g) => filters.backend === "all" || g.backends.includes(filters.backend))
    .filter((g) => filters.model === "all" || g.models.includes(filters.model))
    .filter((g) =>
      filters.invocationCount === "single"
        ? g.count === 1
        : filters.invocationCount === "multi"
          ? g.count > 1
          : true,
    )
    .filter((g) => {
      if (!q) return true;
      const hay = [
        g.class_name ?? "",
        g.root_agent_path ?? "",
        g.hash_content,
        ...g.run_ids,
        ...g.backends,
        ...g.models,
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    })
    .sort((a, b) => b.last_seen - a.last_seen);
}

export function filterAlgorithmRuns(
  groups: AlgorithmGroup[],
  search: string,
  filters: SidebarFilters,
): RunSummary[] {
  const q = search.trim().toLowerCase();
  return groups
    .flatMap((group) =>
      group.runs.map((run) => ({
        ...run,
        algorithm_class: run.algorithm_class ?? group.class_name ?? run.algorithm_class,
      })),
    )
    .filter((run) => withinTime(run.last_event_at, filters.timeRange))
    .filter((run) => filters.state === "all" || run.state === filters.state)
    .filter((run) => filters.className === "all" || run.algorithm_class === filters.className)
    .filter((run) => filters.algorithm === "all" || run.algorithm_class === filters.algorithm)
    .filter((run) => filters.script === "all" || run.script === filters.script)
    .filter((run) => {
      if (!q) return true;
      const hay = [run.algorithm_class ?? "", run.run_id, run.script ?? ""]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
}

export function filterTrainingGroups(
  groups: TrainingGroup[],
  search: string,
  filters: SidebarFilters,
): TrainingGroup[] {
  const q = search.trim().toLowerCase();
  return groups
    .map((group) => ({
      ...group,
      runs: group.runs.filter((run) => {
        if (!withinTime(run.last_event_at, filters.timeRange)) return false;
        if (filters.state !== "all" && run.state !== filters.state) return false;
        if (filters.algorithm !== "all" && group.algorithm_path !== filters.algorithm) return false;
        const trainee = group.class_name ?? group.root_agent_path ?? "";
        if (filters.trainee !== "all" && trainee !== filters.trainee) return false;
        if (!q) return true;
        const hay = [trainee, group.hash_content ?? "", run.run_id, group.algorithm_path ?? ""]
          .join(" ")
          .toLowerCase();
        return hay.includes(q);
      }),
    }))
    .filter((group) => group.runs.length > 0);
}

function FilterPopover({
  rail,
  filters,
  options,
  onChange,
  onClear,
}: {
  rail: SidebarRail;
  filters: SidebarFilters;
  options: FilterOptions;
  onChange: (key: keyof SidebarFilters, value: string) => void;
  onClear: () => void;
}) {
  return (
    <div className="absolute right-2 top-[calc(100%-2px)] z-30 w-64 rounded-md border border-border-strong bg-bg-1 p-3 shadow-[var(--shadow-popover)]">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="text-[10px] font-medium uppercase tracking-[0.08em] text-muted">
          Filters
        </div>
        <button type="button" onClick={onClear} className="text-[11px] text-muted hover:text-text">
          clear
        </button>
      </div>
      <div className="grid gap-2">
        <FilterSelect
          label="Time"
          value={filters.timeRange}
          options={[
            ["all", "All time"],
            ["1h", "Last hour"],
            ["24h", "Last day"],
          ]}
          onChange={(value) => onChange("timeRange", value)}
        />
        <FilterSelect
          label="State"
          value={filters.state}
          options={[
            ["all", "Any state"],
            ["running", "Running"],
            ["ended", "Ended"],
            ["error", "Error"],
          ]}
          onChange={(value) => onChange("state", value)}
        />
        {rail === "agents" ? (
          <>
            <FilterSelect
              label="Class"
              value={filters.className}
              options={[["all", "Any class"], ...options.classes.map((v) => [v, v] as const)]}
              onChange={(value) => onChange("className", value)}
            />
            <FilterSelect
              label="Invocations"
              value={filters.invocationCount}
              options={[
                ["all", "Any count"],
                ["single", "Single"],
                ["multi", "Multiple"],
              ]}
              onChange={(value) => onChange("invocationCount", value)}
            />
            <FilterSelect
              label="Backend"
              value={filters.backend}
              options={[["all", "Any backend"], ...options.backends.map((v) => [v, v] as const)]}
              onChange={(value) => onChange("backend", value)}
            />
            <FilterSelect
              label="Model"
              value={filters.model}
              options={[["all", "Any model"], ...options.models.map((v) => [v, v] as const)]}
              onChange={(value) => onChange("model", value)}
            />
          </>
        ) : null}
        {rail === "algorithms" || rail === "opro" ? (
          <>
            <FilterSelect
              label="Class"
              value={filters.className}
              options={[["all", "Any class"], ...options.classes.map((v) => [v, v] as const)]}
              onChange={(value) => onChange("className", value)}
            />
            <FilterSelect
              label="Script"
              value={filters.script}
              options={[["all", "Any script"], ...options.scripts.map((v) => [v, v] as const)]}
              onChange={(value) => onChange("script", value)}
            />
          </>
        ) : null}
        {rail === "training" ? (
          <>
            <FilterSelect
              label="Optimizer"
              value={filters.algorithm}
              options={[
                ["all", "Any optimizer"],
                ...options.algorithms.map((v) => [v, v] as const),
              ]}
              onChange={(value) => onChange("algorithm", value)}
            />
            <FilterSelect
              label="Trainee"
              value={filters.trainee}
              options={[["all", "Any trainee"], ...options.trainees.map((v) => [v, v] as const)]}
              onChange={(value) => onChange("trainee", value)}
            />
          </>
        ) : null}
      </div>
    </div>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: ReadonlyArray<readonly [string, string]>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-1 text-[11px] text-muted">
      <span>{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-7 rounded border border-border bg-bg px-2 text-[12px] text-text outline-none focus:border-border-strong"
      >
        {options.map(([id, text]) => (
          <option key={id} value={id}>
            {text}
          </option>
        ))}
      </select>
    </label>
  );
}

function countActiveFilters(filters: SidebarFilters, rail: SidebarRail): number {
  const common = [filters.timeRange !== "all", filters.state !== "all"];
  const scoped =
    rail === "agents"
      ? [
          filters.className !== "all",
          filters.invocationCount !== "all",
          filters.backend !== "all",
          filters.model !== "all",
        ]
      : rail === "training"
        ? [filters.algorithm !== "all", filters.trainee !== "all"]
        : [filters.className !== "all", filters.script !== "all"];
  return [...common, ...scoped].filter(Boolean).length;
}

function withinTime(epochSeconds: number, range: SidebarFilters["timeRange"]): boolean {
  if (range === "all") return true;
  const seconds = range === "1h" ? 3600 : 86_400;
  return Date.now() / 1000 - epochSeconds <= seconds;
}

function groupState(group: AgentGroupSummary): SidebarFilters["state"] {
  if (group.running > 0) return "running";
  if (group.errors > 0) return "error";
  return "ended";
}

function unique(values: Array<string | null | undefined>): string[] {
  return [...new Set(values.filter((value): value is string => Boolean(value)))].sort((a, b) =>
    a.localeCompare(b),
  );
}
