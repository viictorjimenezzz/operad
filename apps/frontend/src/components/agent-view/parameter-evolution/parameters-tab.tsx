import { ParameterEvolutionView, WhyPane } from "@/components/agent-view/parameter-evolution";
import {
  ParameterDrawer,
  StructureTree,
  useParameterDrawer,
} from "@/components/agent-view/structure";
import { EmptyState, Metric } from "@/components/ui";
import { dashboardApi } from "@/lib/api/dashboard";
import { type ParameterDescriptor, buildStructureTree } from "@/lib/structure-tree";
import type { AgentGraphResponse, AgentGroupParametersResponse } from "@/lib/types";
import { truncateMiddle } from "@/lib/utils";
import { useQueries, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { z } from "zod";

export interface ParametersTabProps {
  runId?: string;
  hashContent?: string;
  scope: "run" | "group";
}

type EvolutionPoint = {
  runId: string;
  startedAt: number;
  value: unknown;
  hash: string;
  gradient?: {
    message: string;
    severity: "low" | "medium" | "high";
    targetPaths: string[];
    critic?: { agentPath: string; runId: string; langfuseUrl?: string | null };
  };
  sourceTapeStep?: { epoch: number; batch: number; iter: number; optimizerStep: number };
  langfuseUrl?: string | null;
  metricSnapshot?: Record<string, number>;
};

type EvolutionData = {
  path: string;
  type: ParameterDescriptor["type"];
  points: EvolutionPoint[];
};

type SelectedParameter = {
  param: ParameterDescriptor;
  nodePath: string;
  nodeClassName: string;
  nodeHashContent: string | null;
};

export function ParametersTab({ runId, hashContent, scope }: ParametersTabProps) {
  const drawer = useParameterDrawer();
  const group = useQuery({
    queryKey: ["agents", hashContent] as const,
    queryFn: () => {
      if (!hashContent) throw new Error("ParametersTab: hashContent is required");
      return dashboardApi.agentGroup(hashContent);
    },
    enabled: scope === "group" && !!hashContent,
  });
  const sourceRunId = scope === "run" ? runId : (group.data?.runs.at(-1)?.run_id ?? null);

  const graph = useQuery({
    queryKey: ["run", "agent_graph", sourceRunId] as const,
    queryFn: () => {
      if (!sourceRunId) throw new Error("ParametersTab: runId is required");
      return dashboardApi.runAgentGraph(sourceRunId);
    },
    enabled: !!sourceRunId,
  });
  const leafPaths = useMemo(() => leafAgentPaths(graph.data), [graph.data]);
  const parameterQueries = useQueries({
    queries: leafPaths.map((path) => ({
      queryKey: ["run", "agent-parameters", sourceRunId, path] as const,
      queryFn: () => {
        if (!sourceRunId) throw new Error("ParametersTab: runId is required");
        return dashboardApi.agentParameters(sourceRunId, path);
      },
      enabled: !!sourceRunId,
      retry: false,
    })),
  });
  const groupParameters = useQuery({
    queryKey: ["agents", hashContent, "parameters"] as const,
    queryFn: () => {
      if (!hashContent) throw new Error("ParametersTab: hashContent is required");
      return dashboardApi.agentGroupParameters(hashContent);
    },
    enabled: scope === "group" && !!hashContent,
    retry: false,
  });

  const root = useMemo(() => {
    if (!graph.data) return null;
    return buildStructureTree(
      graph.data,
      parameterQueries.map((query) => query.data).filter((data) => data !== undefined),
    );
  }, [graph.data, parameterQueries]);
  const selected = useMemo(
    () => (root && drawer.paramPath ? findParameter(root, drawer.paramPath) : null),
    [root, drawer.paramPath],
  );
  const firstTrainable = useMemo(() => (root ? firstTrainableParameter(root) : null), [root]);
  useEffect(() => {
    if (scope !== "group" || drawer.paramPath || !firstTrainable) return;
    drawer.open(firstTrainable.fullPath);
  }, [scope, drawer, firstTrainable]);
  const runEvolution = useQuery({
    queryKey: ["run", "parameter-evolution", sourceRunId, drawer.paramPath] as const,
    queryFn: () => {
      if (!sourceRunId || !drawer.paramPath) {
        throw new Error("ParametersTab: parameter evolution requires a run and path");
      }
      return fetchParameterEvolution(sourceRunId, drawer.paramPath);
    },
    enabled: scope === "run" && !!sourceRunId && !!drawer.paramPath,
    retry: false,
  });
  const groupEvolution = useMemo(
    () =>
      selected && groupParameters.data
        ? groupEvolutionFor(selected.param, groupParameters.data)
        : null,
    [selected, groupParameters.data],
  );

  if (scope === "run" && !runId) {
    return <EmptyState title="missing run id" description="parameter evolution needs a run id" />;
  }
  if (scope === "group" && !hashContent) {
    return (
      <EmptyState
        title="missing agent hash"
        description="parameter evolution needs an agent group"
      />
    );
  }
  if (group.isLoading || graph.isLoading || parameterQueries.some((query) => query.isLoading)) {
    return <LoadingPanel />;
  }
  if (graph.error || !root) {
    return (
      <EmptyState
        title="agent graph unavailable"
        description="this run has not produced the agent graph needed for parameter inspection"
      />
    );
  }

  const trainableCount = countTrainableParameters(root);
  if (trainableCount === 0) {
    return (
      <EmptyState
        title="no trainable parameters"
        description={
          scope === "run"
            ? "this run has no trainable parameters; the algorithm has no gradient targets"
            : "this group has no trainable parameters; the algorithm has no gradient targets"
        }
      />
    );
  }

  const evolution = scope === "run" ? runEvolution.data : groupEvolution;
  const evolutionLoading =
    drawer.paramPath != null &&
    (scope === "run" ? runEvolution.isLoading : groupParameters.isLoading);
  const selectedStep = effectiveStep(drawer.stepIndex, evolution?.points.length ?? 0);
  const point = selectedStep == null ? null : (evolution?.points[selectedStep] ?? null);
  const previousPoint =
    selectedStep != null && selectedStep > 0 ? (evolution?.points[selectedStep - 1] ?? null) : null;
  const subtitle = drawerSubtitle(selected);
  const detail = evolutionLoading ? (
    <LoadingPanel />
  ) : evolution ? (
    <div className="min-h-full">
      <ParameterEvolutionView
        path={evolution.path}
        type={evolution.type}
        points={evolution.points}
        selectedStep={selectedStep}
        onSelectStep={drawer.selectStep}
      />
      {scope === "run" ? (
        <WhyPane point={point} previous={previousPoint} />
      ) : (
        <EmptyState
          title="open a run for gradient context"
          description={`this view aggregates across ${evolution.points.length} invocations; open a run for full gradient context`}
          className="min-h-32 border-t border-border"
        />
      )}
    </div>
  ) : (
    <EmptyState
      title="parameter history unavailable"
      description="this parameter has not emitted evolution points yet"
    />
  );

  if (scope === "group") {
    return (
      <div className="grid h-full min-h-0 grid-cols-1 overflow-hidden border border-border bg-bg-1 lg:grid-cols-[minmax(320px,0.45fr)_minmax(0,1fr)]">
        <div className="flex min-h-0 flex-col">
          <header className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-border px-3 py-2">
            <Metric label="trainable params" value={trainableCount} />
            <Metric label="leaf agents" value={leafPaths.length} />
            <Metric label="group" value={truncateMiddle(hashContent ?? "", 14)} />
          </header>
          <div className="min-h-0 flex-1">
            <StructureTree
              root={root}
              selectedParamPath={drawer.paramPath}
              onSelectParameter={(param) => drawer.open(param.fullPath)}
            />
          </div>
        </div>
        <section className="flex min-h-0 flex-col border-t border-border bg-bg lg:border-l lg:border-t-0">
          <header className="flex items-start gap-3 border-b border-border px-4 py-3">
            <div className="min-w-0 flex-1">
              <div className="truncate text-[16px] font-medium text-text">
                {selected?.param.path ?? drawer.paramPath ?? "parameter"}
              </div>
              {subtitle ? (
                <div className="mt-1 truncate font-mono text-[11px] text-muted-2">{subtitle}</div>
              ) : null}
            </div>
          </header>
          <div className="min-h-0 flex-1 overflow-auto">{detail}</div>
        </section>
      </div>
    );
  }

  return (
    <div className="h-full min-h-0 overflow-hidden">
      <div className="flex h-full min-h-0 flex-col border border-border bg-bg-1">
        <header className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-border px-3 py-2">
          <Metric label="trainable params" value={trainableCount} />
          <Metric label="leaf agents" value={leafPaths.length} />
          <Metric
            label={scope === "run" ? "run" : "group"}
            value={truncateMiddle(scope === "run" ? (sourceRunId ?? "") : (hashContent ?? ""), 14)}
          />
        </header>
        <div className="min-h-0 flex-1">
          <StructureTree
            root={root}
            selectedParamPath={drawer.paramPath}
            onSelectParameter={(param) => drawer.open(param.fullPath)}
          />
        </div>
      </div>

      <ParameterDrawer
        open={drawer.paramPath != null}
        identity={hashContent ?? selected?.nodeHashContent ?? sourceRunId ?? "parameters"}
        title={selected?.param.path ?? drawer.paramPath ?? "parameter"}
        {...(subtitle ? { subtitle } : {})}
        onClose={drawer.close}
      >
        {detail}
      </ParameterDrawer>
    </div>
  );
}

function LoadingPanel() {
  return (
    <div className="h-full p-4">
      <div className="h-full min-h-40 animate-pulse bg-bg-2" />
    </div>
  );
}

function leafAgentPaths(graph: AgentGraphResponse | undefined): string[] {
  if (!graph) return [];
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

function countTrainableParameters(root: ReturnType<typeof buildStructureTree>): number {
  let total = root.parameters.filter((param) => param.requiresGrad).length;
  for (const child of root.children) total += countTrainableParameters(child);
  return total;
}

function firstTrainableParameter(
  root: ReturnType<typeof buildStructureTree>,
): ParameterDescriptor | null {
  const direct = root.parameters.find((param) => param.requiresGrad);
  if (direct) return direct;
  for (const child of root.children) {
    const match = firstTrainableParameter(child);
    if (match) return match;
  }
  return null;
}

function findParameter(
  root: ReturnType<typeof buildStructureTree>,
  fullPath: string,
): SelectedParameter | null {
  for (const param of root.parameters) {
    if (param.fullPath === fullPath) {
      return {
        param,
        nodePath: root.path,
        nodeClassName: root.className,
        nodeHashContent: root.hashContent,
      };
    }
  }
  for (const child of root.children) {
    const match = findParameter(child, fullPath);
    if (match) return match;
  }
  return null;
}

function drawerSubtitle(selected: SelectedParameter | null): string | undefined {
  if (!selected) return undefined;
  return `${selected.nodeClassName} ${selected.nodePath} - ${selected.param.type}`;
}

function effectiveStep(stepIndex: number | null, pointCount: number): number | null {
  if (pointCount === 0) return null;
  if (stepIndex == null) return pointCount - 1;
  return Math.max(0, Math.min(stepIndex, pointCount - 1));
}

function groupEvolutionFor(
  param: ParameterDescriptor,
  response: AgentGroupParametersResponse,
): EvolutionData {
  const points = response.series
    .map((row) => {
      const entry = groupValueForParam(row.values, param);
      if (!entry) return null;
      return {
        runId: row.run_id,
        startedAt: row.started_at,
        value: entry.value,
        hash: entry.hash,
      };
    })
    .filter((point): point is EvolutionPoint => point !== null)
    .sort((a, b) => a.startedAt - b.startedAt);

  return {
    path: param.fullPath,
    type: param.type,
    points,
  };
}

function groupValueForParam(
  values: Record<string, { value?: unknown; hash: string }>,
  param: ParameterDescriptor,
): { value?: unknown; hash: string } | null {
  return values[param.fullPath] ?? values[param.path] ?? null;
}

const GradientSchema = z
  .object({
    message: z.string().default(""),
    severity: z.enum(["low", "medium", "high"]).default("low"),
    target_paths: z.array(z.string()).default([]),
    critic: z
      .object({
        agent_path: z.string().default(""),
        run_id: z.string().default(""),
        langfuse_url: z.string().nullable().optional(),
      })
      .nullable()
      .optional(),
  })
  .transform((value) => ({
    message: value.message,
    severity: value.severity,
    targetPaths: value.target_paths,
    ...(value.critic
      ? {
          critic: {
            agentPath: value.critic.agent_path,
            runId: value.critic.run_id,
            langfuseUrl: value.critic.langfuse_url ?? null,
          },
        }
      : {}),
  }));

const TapeStepSchema = z
  .object({
    epoch: z.number(),
    batch: z.number(),
    iter: z.number(),
    optimizer_step: z.number(),
  })
  .transform((value) => ({
    epoch: value.epoch,
    batch: value.batch,
    iter: value.iter,
    optimizerStep: value.optimizer_step,
  }));

const EvolutionResponseSchema = z
  .object({
    path: z.string(),
    type: z.enum(["text", "rule_list", "example_list", "float", "categorical", "configuration"]),
    points: z
      .array(
        z
          .object({
            run_id: z.string(),
            started_at: z.number(),
            value: z.unknown(),
            hash: z.string(),
            gradient: GradientSchema.nullable().optional(),
            source_tape_step: TapeStepSchema.nullable().optional(),
            langfuse_url: z.string().nullable().optional(),
            metric_snapshot: z.record(z.number()).nullable().optional(),
          })
          .transform((value) => ({
            runId: value.run_id,
            startedAt: value.started_at,
            value: value.value,
            hash: value.hash,
            ...(value.gradient ? { gradient: value.gradient } : {}),
            ...(value.source_tape_step ? { sourceTapeStep: value.source_tape_step } : {}),
            langfuseUrl: value.langfuse_url ?? null,
            ...(value.metric_snapshot ? { metricSnapshot: value.metric_snapshot } : {}),
          })),
      )
      .default([]),
  })
  .transform((value) => ({
    path: value.path,
    type: value.type,
    points: value.points,
  }));

async function fetchParameterEvolution(runId: string, path: string): Promise<EvolutionData> {
  const response = await fetch(
    `/runs/${encodeURIComponent(runId)}/parameter-evolution/${encodeURIComponent(path)}`,
    { headers: { accept: "application/json" } },
  );
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText} <- parameter evolution`);
  }
  return EvolutionResponseSchema.parse(await response.json());
}
