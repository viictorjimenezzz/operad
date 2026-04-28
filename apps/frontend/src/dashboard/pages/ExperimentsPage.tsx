import {
  HashDiffSection,
  IdentityStripSection,
  LangfuseLinksSection,
  OpLogSection,
  OutcomesSection,
  ParameterDiffSection,
  type CompareParameter,
  type CompareRun,
} from "@/components/agent-view/compare";
import { EmptyState } from "@/components/ui/empty-state";
import { dashboardApi } from "@/lib/api/dashboard";
import type { HashKey } from "@/components/ui";
import type { AgentGraphResponse, Envelope } from "@/lib/types";
import { useQueries } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";

const MAX_COLUMNS = 4;

export function parseRunsParam(raw: string | null): string[] {
  if (!raw) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const piece of raw.split(",")) {
    const id = piece.trim();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(id);
  }
  return out;
}

export function resolveComparisonRunIds(raw: string | null): string[] {
  return parseRunsParam(raw);
}

export function updateRunsSearch(current: URLSearchParams, nextRunIds: string[]): URLSearchParams {
  const next = new URLSearchParams(current);
  if (nextRunIds.length === 0) next.delete("runs");
  else next.set("runs", [...new Set(nextRunIds)].join(","));
  return next;
}

export function ExperimentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedRunIds = resolveComparisonRunIds(searchParams.get("runs"));
  const visibleRunIds = selectedRunIds.slice(0, MAX_COLUMNS);

  const compareQueries = useQueries({
    queries: visibleRunIds.map((runId) => ({
      queryKey: ["experiments", "compare", runId] as const,
      queryFn: () => loadCompareRun(runId),
      retry: false,
    })),
  });

  const loading = compareQueries.some((query) => query.isPending);
  const runs = useMemo(
    () =>
      compareQueries
        .filter((query): query is typeof query & { data: CompareRun } => query.isSuccess)
        .map((query) => query.data),
    [compareQueries],
  );

  function setRunIds(nextRunIds: string[]) {
    setSearchParams(updateRunsSearch(searchParams, nextRunIds));
  }

  function removeRun(runId: string) {
    setRunIds(selectedRunIds.filter((current) => current !== runId));
  }

  if (selectedRunIds.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState
          title="no runs selected"
          description="select two or more rows, then click Compare"
          cta={
            <Link
              to="/algorithms"
              className="rounded border border-accent bg-accent-dim px-3 py-1.5 text-xs text-text hover:bg-accent/20"
            >
              go to algorithms
            </Link>
          }
        />
      </div>
    );
  }

  if (loading) {
    return <div className="p-4 text-xs text-muted">loading comparison…</div>;
  }

  return (
    <div className="flex h-full flex-col gap-3 overflow-auto p-3">
      <div className="flex flex-wrap items-center gap-2 border-b border-border pb-2">
        <div className="text-[11px] uppercase tracking-[0.08em] text-muted">Compare runs</div>
        {selectedRunIds.map((runId) => (
          <button
            key={runId}
            type="button"
            onClick={() => removeRun(runId)}
            className="inline-flex items-center gap-2 rounded border border-border bg-bg-2 px-2 py-1 font-mono text-[11px] text-text"
          >
            {runId}
            <span className="text-muted">x</span>
          </button>
        ))}
        {selectedRunIds.length > MAX_COLUMNS ? (
          <span className="rounded border border-[--color-warn] bg-[--color-warn]/15 px-2 py-1 text-[11px] text-text">
            select fewer to compare side by side
          </span>
        ) : null}
      </div>

      {runs.length === 0 ? (
        <EmptyState
          title="comparison unavailable"
          description="none of the selected runs could be loaded"
        />
      ) : (
        <>
          <IdentityStripSection runs={runs} />
          <HashDiffSection runs={runs} />
          <ParameterDiffSection runs={runs} />
          <OpLogSection runs={runs} />
          <OutcomesSection runs={runs} />
          <LangfuseLinksSection runs={runs} />
        </>
      )}
    </div>
  );
}

async function loadCompareRun(runId: string): Promise<CompareRun> {
  const summary = await dashboardApi.runSummary(runId);

  const [invocations, events, parameters] = await Promise.all([
    dashboardApi.runInvocations(runId).catch(() => ({ invocations: [] })),
    dashboardApi.runEvents(runId, 500).catch(() => ({ events: [] })),
    loadTrainableParameters(runId).catch(() => []),
  ]);

  const latestInvocation = invocations.invocations[invocations.invocations.length - 1] ?? null;
  const hashContent =
    summary.hash_content ?? latestInvocation?.hash_content ?? summary.root_agent_path ?? summary.run_id;

  return {
    runId,
    summary,
    latestInvocation,
    parameters,
    ops: extractOps(events.events),
    hashContent,
    langfuseUrl: latestInvocation?.langfuse_url ?? null,
    hashes: hashesFor(summary, latestInvocation?.hash_content ?? null),
  };
}

function hashesFor(
  run: CompareRun["summary"],
  invocationHashContent: string | null,
): Partial<Record<HashKey, string | null>> {
  return {
    hash_model: run.hash_model ?? null,
    hash_prompt: run.hash_prompt ?? null,
    hash_input: run.hash_input ?? null,
    hash_output_schema: run.hash_output_schema ?? null,
    hash_config: run.hash_config ?? null,
    hash_graph: run.hash_graph ?? null,
    hash_content: run.hash_content ?? invocationHashContent ?? null,
  };
}

async function loadTrainableParameters(runId: string): Promise<CompareParameter[]> {
  const graph = await dashboardApi.runAgentGraph(runId);
  const leafPaths = leafAgentPaths(graph);
  if (leafPaths.length === 0) return [];

  const responses = await Promise.all(
    leafPaths.map((path) => dashboardApi.agentParameters(runId, path).catch(() => null)),
  );

  const rows: CompareParameter[] = [];
  for (const response of responses) {
    if (!response) continue;
    for (const parameter of response.parameters) {
      if (!parameter.requires_grad) continue;
      rows.push({
        fullPath: `${response.agent_path}.${parameter.path}`,
        type: parameter.type,
        value: parameter.value,
      });
    }
  }

  rows.sort((a, b) => a.fullPath.localeCompare(b.fullPath));
  return rows;
}

function leafAgentPaths(graph: AgentGraphResponse): string[] {
  const parents = new Set(
    graph.nodes
      .map((node) => node.parent_path)
      .filter((path): path is string => typeof path === "string" && path.length > 0),
  );
  return graph.nodes
    .filter((node) => !parents.has(node.path))
    .map((node) => node.path)
    .sort((a, b) => a.localeCompare(b));
}

function extractOps(events: Envelope[]): string[] {
  const out: string[] = [];
  for (const event of events) {
    if (event.type !== "algo_event") continue;
    out.push(...extractOpsFromValue(event.metadata));
    out.push(...extractOpsFromValue(event.payload));
  }
  return dedupe(out);
}

function extractOpsFromValue(value: unknown): string[] {
  if (!isRecord(value)) return [];
  const candidates = [value.ops, value.operations, value.mutations];
  const out: string[] = [];
  for (const candidate of candidates) {
    if (!Array.isArray(candidate)) continue;
    for (const item of candidate) {
      const formatted = formatOp(item);
      if (formatted) out.push(formatted);
    }
  }
  return out;
}

function formatOp(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (!isRecord(value)) return null;

  const name = stringValue(value.type) ?? stringValue(value.op) ?? stringValue(value.kind) ?? "Op";
  const path = stringValue(value.path) ?? stringValue(value.target_path);
  const rule = stringValue(value.rule);
  const from = value.from;
  const to = value.to;

  const args: string[] = [];
  if (path) args.push(`path=${quoted(path)}`);
  if (rule) args.push(`rule=${quoted(rule)}`);
  if (from !== undefined) args.push(`from=${short(from)}`);
  if (to !== undefined) args.push(`to=${short(to)}`);

  const prefix =
    name.toLowerCase().includes("append")
      ? "+"
      : name.toLowerCase().includes("edit") || name.toLowerCase().includes("set")
        ? "~"
        : "•";

  return `${prefix} ${name}(${args.join(", ")})`;
}

function quoted(value: string): string {
  return `"${value.replaceAll('"', "'")}"`;
}

function short(value: unknown): string {
  if (typeof value === "string") return quoted(value.length > 64 ? `${value.slice(0, 61)}...` : value);
  if (typeof value === "number" || typeof value === "boolean" || value == null) return String(value);
  try {
    const rendered = JSON.stringify(value);
    return rendered && rendered.length > 64 ? `${rendered.slice(0, 61)}...` : (rendered ?? "null");
  } catch {
    return String(value);
  }
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value != null && typeof value === "object" && !Array.isArray(value);
}

function dedupe(values: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of values) {
    if (seen.has(value)) continue;
    seen.add(value);
    out.push(value);
  }
  return out;
}
