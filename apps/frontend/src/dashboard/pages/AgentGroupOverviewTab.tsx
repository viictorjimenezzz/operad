import { AgentGroupIdentityCard } from "@/components/agent-view/group/identity-card";
import {
  Eyebrow,
  Metric,
  MultiSeriesChart,
  PanelGrid,
  PanelGridItem,
  Pill,
} from "@/components/ui";
import { type HashKey, HashRow } from "@/components/ui/hash-row";
import { useAgentGroup, useAgentMeta } from "@/hooks/use-runs";
import { dashboardApi } from "@/lib/api/dashboard";
import type { AgentMetaResponse, RunInvocation, RunSummary } from "@/lib/types";
import { cn, formatCost, formatDurationMs, formatTokens } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { useParams } from "react-router-dom";

type ToggleKey = "latency" | "cost" | "tokens";

type SchemaField = {
  name: string;
  type: string;
  description: string;
  required: boolean;
  hasDefault: boolean;
  defaultValue: unknown;
  enumValues: unknown[] | null;
  system: boolean;
};

type TypeSchema = {
  key: string;
  name: string;
  fields: SchemaField[];
};

const SERIES_COLORS: Record<ToggleKey, string> = {
  latency: "var(--qual-1)",
  cost: "var(--qual-3)",
  tokens: "var(--qual-5)",
};

const REPRO_KEYS: HashKey[] = [
  "hash_prompt_template",
  "hash_input_schema",
  "hash_output_schema",
  "hash_config",
  "hash_graph",
  "hash_model",
  "hash_content",
];

export function AgentGroupOverviewTab() {
  const { hashContent } = useParams<{ hashContent: string }>();
  const group = useAgentGroup(hashContent);
  const latestRun = group.data?.runs.at(-1) ?? null;
  const meta = useAgentMeta(latestRun?.run_id ?? null, latestRun?.root_agent_path ?? null);
  const prompts = useQuery({
    queryKey: ["agent-prompts", latestRun?.run_id, latestRun?.root_agent_path, "template"] as const,
    queryFn: () => {
      if (!latestRun?.run_id || !latestRun.root_agent_path) {
        throw new Error("prompt template needs a run and root agent path");
      }
      return dashboardApi.agentPrompts(latestRun.run_id, latestRun.root_agent_path);
    },
    enabled: !!latestRun?.run_id && !!latestRun.root_agent_path,
    staleTime: 30_000,
    retry: false,
  });
  const invocations = useQuery({
    queryKey: ["run", "invocations", latestRun?.run_id] as const,
    queryFn: () => {
      if (!latestRun?.run_id) throw new Error("invocations need a run id");
      return dashboardApi.runInvocations(latestRun.run_id);
    },
    enabled: !!latestRun?.run_id,
    staleTime: 30_000,
    retry: false,
  });
  const reproducibility = useQuery({
    queryKey: ["agents", hashContent, "reproducibility"] as const,
    queryFn: () => {
      if (!hashContent) throw new Error("reproducibility needs an agent hash");
      return dashboardApi.agentGroupReproducibility(hashContent);
    },
    enabled: !!hashContent,
    staleTime: 30_000,
    retry: false,
  });
  const [visible, setVisible] = useState<Set<ToggleKey>>(new Set(["latency", "cost", "tokens"]));

  if (!hashContent || !group.data) return null;
  const detail = group.data;
  const runs = [...detail.runs].sort((a, b) => a.started_at - b.started_at);
  const successRate = detail.count > 0 ? Math.max(0, 1 - detail.errors / detail.count) : 0;
  const latencyP50 = median(detail.latencies);
  const totalTokens = detail.prompt_tokens + detail.completion_tokens;
  const systemPrompt =
    prompts.data?.entries.at(-1)?.system ?? fallbackSystemPrompt(meta.data ?? null);
  const renderer = prompts.data?.renderer ?? stringValue(meta.data?.config?.io?.renderer) ?? "xml";
  const latestInvocation = invocations.data?.invocations.at(-1) ?? null;

  function toggleMetric(key: ToggleKey) {
    setVisible((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mx-auto max-w-[1280px] space-y-4">
        <AgentGroupIdentityCard group={detail} meta={meta.data} />
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-border pb-3">
          <Metric label="runs" value={detail.count} />
          <Metric label="ok" value={`${Math.round(successRate * 100)}%`} />
          <Metric label="p50" value={formatDurationMs(latencyP50)} />
          <Metric label="tokens" value={formatTokens(totalTokens)} />
          <Metric label="cost" value={formatCost(detail.cost_usd)} />
          <Metric
            label="state"
            value={detail.running > 0 ? "live" : detail.errors > 0 ? "error" : "ended"}
          />
        </div>
        <PanelGrid cols={3} gap="md">
          <PanelGridItem colSpan={2}>
            <ContractCard meta={meta.data ?? null} />
          </PanelGridItem>
          <ConfigCard meta={meta.data ?? null} latestRun={latestRun} />
          <PanelGridItem colSpan={2}>
            <PromptTemplateCard
              meta={meta.data ?? null}
              systemPrompt={systemPrompt}
              inputSchema={parseTypeSchema(meta.data?.input_schema)}
              latestInvocation={latestInvocation}
              renderer={renderer}
              loading={prompts.isLoading}
            />
          </PanelGridItem>
          <InvocationTrendCard runs={runs} visible={visible} onToggleMetric={toggleMetric} />
          <PanelGridItem colSpan={3}>
            <OverviewTile title="REPRODUCIBILITY">
              {reproducibility.isLoading ? (
                <div className="text-[12px] text-muted-2">loading hashes...</div>
              ) : (
                <HashRow
                  current={reproducibility.data?.hashes ?? {}}
                  keys={REPRO_KEYS}
                  size="md"
                />
              )}
            </OverviewTile>
          </PanelGridItem>
        </PanelGrid>
      </div>
    </div>
  );
}

function OverviewTile({
  title,
  toolbar,
  minHeight,
  children,
}: {
  title: ReactNode;
  toolbar?: ReactNode;
  minHeight?: number;
  children: ReactNode;
}) {
  return (
    <section className="flex h-full flex-col rounded-lg border border-border bg-bg-1 shadow-[var(--shadow-card-soft)]">
      <div className="flex items-center gap-3 px-3 py-3">
        <div className="min-w-0 flex-1 truncate text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
          {title}
        </div>
        {toolbar ? <div className="flex shrink-0 items-center gap-2">{toolbar}</div> : null}
      </div>
      <div className="min-h-0 flex-1 p-3 pt-0" style={minHeight ? { minHeight } : undefined}>
        {children}
      </div>
    </section>
  );
}

function ContractCard({ meta }: { meta: AgentMetaResponse | null }) {
  const input = parseTypeSchema(meta?.input_schema);
  const output = parseTypeSchema(meta?.output_schema);
  return (
    <OverviewTile title="CONTRACT" minHeight={280}>
      <div className="grid max-h-[270px] gap-3 overflow-auto md:grid-cols-2">
        <SchemaPane label="input" schema={input} />
        <SchemaPane label="output" schema={output} />
      </div>
    </OverviewTile>
  );
}

function SchemaPane({ label, schema }: { label: string; schema: TypeSchema | null }) {
  if (!schema) {
    return (
      <div className="rounded-md border border-border bg-bg-inset p-3">
        <Eyebrow>{label}</Eyebrow>
        <div className="mt-2 text-[12px] text-muted-2">schema unavailable</div>
      </div>
    );
  }
  return (
    <div className="rounded-md border border-border bg-bg-inset p-3">
      <div className="flex items-baseline justify-between gap-3">
        <Eyebrow>{label}</Eyebrow>
        <span className="truncate font-mono text-[12px] text-text" title={schema.key}>
          {schema.name}
        </span>
      </div>
      <div className="mt-3 divide-y divide-border">
        {schema.fields.length > 0 ? (
          schema.fields.map((field) => <FieldRow key={field.name} field={field} />)
        ) : (
          <div className="py-2 text-[12px] text-muted-2">no fields</div>
        )}
      </div>
    </div>
  );
}

function FieldRow({ field }: { field: SchemaField }) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 py-2 first:pt-0 last:pb-0">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-[12px] font-medium text-text">{field.name}</span>
          <span className="font-mono text-[11px] text-muted-2">{field.type}</span>
          {field.system ? (
            <Pill tone="accent" size="sm">
              system
            </Pill>
          ) : null}
        </div>
        {field.description ? (
          <div className="mt-1 text-[12px] leading-5 text-muted">{field.description}</div>
        ) : null}
        {field.enumValues && field.enumValues.length > 0 ? (
          <div className="mt-1 truncate font-mono text-[10px] text-muted-2">
            enum {field.enumValues.map(String).join(", ")}
          </div>
        ) : null}
      </div>
      <div className="flex flex-col items-end gap-1">
        <span className="font-mono text-[10px] uppercase tracking-[0.06em] text-muted-2">
          {field.required ? "required" : "optional"}
        </span>
        {field.hasDefault ? (
          <span className="max-w-28 truncate font-mono text-[10px] text-muted-2">
            default {formatDefault(field.defaultValue)}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function ConfigCard({
  meta,
  latestRun,
}: {
  meta: AgentMetaResponse | null;
  latestRun: RunSummary | null;
}) {
  const cfg = meta?.config ?? null;
  const rows: Array<[string, string]> = [
    ["backend", cfg?.backend ?? latestRun?.backend ?? "—"],
    ["model", cfg?.model ?? latestRun?.model ?? "—"],
    ["renderer", stringValue(cfg?.io?.renderer) ?? "—"],
    ["temperature", numberOrDash(cfg?.sampling?.temperature)],
    ["max tokens", numberOrDash(cfg?.sampling?.max_tokens)],
    ["timeout", numberOrDash(cfg?.resilience?.timeout)],
    ["retries", numberOrDash(cfg?.resilience?.max_retries)],
  ];
  const trainable = meta?.trainable_paths ?? [];
  return (
    <OverviewTile title="CONFIGURATION" minHeight={280}>
      <div className="grid max-h-[270px] grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-2 overflow-auto">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <span className="text-[10px] uppercase tracking-[0.06em] text-muted-2">{label}</span>
            <span className="min-w-0 truncate font-mono text-[12px] text-text" title={value}>
              {value}
            </span>
          </div>
        ))}
      </div>
      {trainable.length > 0 ? (
        <div className="mt-3 text-[11px] text-muted-2">
          {trainable.length} trainable path{trainable.length === 1 ? "" : "s"}
        </div>
      ) : null}
    </OverviewTile>
  );
}

function PromptTemplateCard({
  meta,
  systemPrompt,
  inputSchema,
  latestInvocation,
  renderer,
  loading,
}: {
  meta: AgentMetaResponse | null;
  systemPrompt: string | null;
  inputSchema: TypeSchema | null;
  latestInvocation: RunInvocation | null;
  renderer: string;
  loading: boolean;
}) {
  const rows = promptRows(meta, inputSchema, latestInvocation);
  return (
    <OverviewTile title={`SYSTEM PROMPT · ${renderer.toUpperCase()}`} minHeight={340}>
      {loading ? (
        <div className="mb-3 text-[12px] text-muted-2">loading prompt template...</div>
      ) : null}
      <div className="max-h-[380px] overflow-auto rounded-md border border-border bg-bg-inset">
        {rows.length > 0 ? (
          rows.map((row) => <PromptFieldRow key={`${row.scope}:${row.name}`} row={row} />)
        ) : (
          <pre className="whitespace-pre-wrap p-3 font-mono text-[11px] leading-5 text-text">
            {systemPrompt ?? "—"}
          </pre>
        )}
      </div>
    </OverviewTile>
  );
}

type PromptRow = {
  scope: string;
  name: string;
  type: string;
  description: string;
  value: string;
};

function PromptFieldRow({ row }: { row: PromptRow }) {
  return (
    <div className="grid gap-3 border-b border-border p-3 last:border-b-0 md:grid-cols-[180px_minmax(0,1fr)]">
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-[0.06em] text-muted-2">{row.scope}</div>
        <div className="mt-1 flex flex-wrap items-baseline gap-2">
          <span className="font-mono text-[12px] text-text">{row.name}</span>
          <span className="font-mono text-[11px] text-muted-2">{row.type}</span>
        </div>
        {row.description ? (
          <div className="mt-1 text-[12px] leading-5 text-muted">{row.description}</div>
        ) : null}
      </div>
      <pre className="min-w-0 whitespace-pre-wrap font-mono text-[11px] leading-5 text-text">
        {row.value || "—"}
      </pre>
    </div>
  );
}

function promptRows(
  meta: AgentMetaResponse | null,
  inputSchema: TypeSchema | null,
  latestInvocation: RunInvocation | null,
): PromptRow[] {
  const rows: PromptRow[] = [];
  if (meta?.role?.trim()) {
    rows.push({
      scope: "system",
      name: "role",
      type: "str",
      description: "Persona the agent adopts for every call.",
      value: meta.role.trim(),
    });
  }
  if (meta?.task?.trim()) {
    rows.push({
      scope: "system",
      name: "task",
      type: "str",
      description: "Objective accomplished on each invocation.",
      value: meta.task.trim(),
    });
  }
  if (meta && meta.rules.length > 0) {
    rows.push({
      scope: "system",
      name: "rules",
      type: "list[str]",
      description: "Hard constraints the agent must obey.",
      value: meta.rules.map((rule) => `- ${rule}`).join("\n"),
    });
  }
  const input = isRecord(latestInvocation?.input) ? latestInvocation.input : {};
  for (const field of inputSchema?.fields ?? []) {
    if (field.system) continue;
    rows.push({
      scope: "input",
      name: field.name,
      type: field.type,
      description: field.description,
      value: formatPromptValue(input[field.name]),
    });
  }
  return rows;
}

function InvocationTrendCard({
  runs,
  visible,
  onToggleMetric,
}: {
  runs: RunSummary[];
  visible: Set<ToggleKey>;
  onToggleMetric: (key: ToggleKey) => void;
}) {
  const series = buildSeries(runs, visible);
  const showChart = runs.length >= 2 && series.length > 0;
  return (
    <OverviewTile
      title={`${runs.length} INVOCATION${runs.length === 1 ? "" : "S"}`}
      minHeight={320}
      toolbar={
        <div className="flex gap-1">
          {(["latency", "cost", "tokens"] as ToggleKey[]).map((key) => {
            const active = visible.has(key);
            return (
              <button
                key={key}
                type="button"
                onClick={() => onToggleMetric(key)}
                aria-pressed={active}
                className={cn(
                  "rounded border px-1.5 py-0.5 text-[10px] font-medium transition-colors",
                  active
                    ? "border-accent/40 bg-accent/15 text-accent"
                    : "border-border bg-bg-2 text-muted hover:border-border-strong hover:text-text",
                )}
              >
                {key}
              </button>
            );
          })}
        </div>
      }
    >
      {showChart ? (
        <MultiSeriesChart series={series} height={260} xLabel="invocation" />
      ) : (
        <div className="flex h-[260px] flex-col justify-center gap-3 rounded-md border border-border bg-bg-inset p-4">
          <div className="text-[13px] font-medium text-text">No varying trend yet</div>
          <div className="text-[12px] leading-5 text-muted">
            This card fills in once the instance has multiple non-zero metric samples.
          </div>
        </div>
      )}
    </OverviewTile>
  );
}

function buildSeries(runs: RunSummary[], visible: Set<ToggleKey>) {
  const defs: Array<{ key: ToggleKey; getValue: (r: RunSummary) => number | null }> = [
    { key: "latency", getValue: (r) => r.duration_ms },
    { key: "cost", getValue: (r) => r.cost?.cost_usd ?? null },
    {
      key: "tokens",
      getValue: (r) =>
        r.prompt_tokens || r.completion_tokens ? r.prompt_tokens + r.completion_tokens : null,
    },
  ];
  return defs
    .filter((d) => visible.has(d.key))
    .map((d) => {
      const points = runs.map((run, index) => ({ x: index + 1, y: d.getValue(run) }));
      return {
        id: d.key,
        label: d.key,
        color: SERIES_COLORS[d.key],
        points,
        empty: points.every((p) => p.y == null || p.y === 0),
      };
    })
    .filter((series) => !series.empty);
}

function parseTypeSchema(raw: unknown): TypeSchema | null {
  if (!isRecord(raw)) return null;
  const fieldsRaw = Array.isArray(raw.fields) ? raw.fields : [];
  return {
    key: stringValue(raw.key) ?? stringValue(raw.name) ?? "schema",
    name: stringValue(raw.name) ?? stringValue(raw.key)?.split(".").at(-1) ?? "Schema",
    fields: fieldsRaw.filter(isRecord).map(
      (field): SchemaField => ({
        name: stringValue(field.name) ?? "field",
        type: stringValue(field.type) ?? "unknown",
        description: stringValue(field.description) ?? "",
        required: booleanValue(field.required),
        hasDefault: booleanValue(field.has_default),
        defaultValue: field.default,
        enumValues: Array.isArray(field.enum_values) ? field.enum_values : null,
        system: booleanValue(field.system),
      }),
    ),
  };
}

function fallbackSystemPrompt(meta: AgentMetaResponse | null): string | null {
  if (!meta) return null;
  const chunks: string[] = [];
  if (meta.role?.trim()) chunks.push(`<role>\n${meta.role.trim()}\n</role>`);
  if (meta.task?.trim()) chunks.push(`<task>\n${meta.task.trim()}\n</task>`);
  if (meta.rules.length > 0) {
    chunks.push(`<rules>\n${meta.rules.map((rule) => `- ${rule}`).join("\n")}\n</rules>`);
  }
  return chunks.length > 0 ? chunks.join("\n\n") : null;
}

function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2
    ? (sorted[mid] ?? null)
    : ((sorted[mid - 1] ?? 0) + (sorted[mid] ?? 0)) / 2;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function booleanValue(value: unknown): boolean {
  return value === true;
}

function numberOrDash(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) ? String(value) : "—";
}

function formatDefault(value: unknown): string {
  if (value === undefined) return "undefined";
  if (value === null) return "null";
  if (typeof value === "string") return value === "" ? '""' : value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return Array.isArray(value) ? `[${value.length}]` : "{...}";
}

function formatPromptValue(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value, null, 2);
}
