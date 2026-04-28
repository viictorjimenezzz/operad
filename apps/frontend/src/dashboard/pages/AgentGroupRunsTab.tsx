import { Button, type RunRow, RunTable, type RunTableColumn } from "@/components/ui";
import { useAgentGroup } from "@/hooks/use-runs";
import type { RunSummary } from "@/lib/types";
import { useUIStore } from "@/stores";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

const columns: RunTableColumn[] = [
  { id: "state", label: "State", source: "_state", sortable: true, width: 80 },
  { id: "run", label: "Run id", source: "_id", sortable: true, width: 130 },
  {
    id: "started",
    label: "Started",
    source: "_started",
    sortable: true,
    defaultSort: "desc",
    width: 92,
  },
  {
    id: "latency",
    label: "Latency",
    source: "_duration",
    align: "right",
    sortable: true,
    width: 86,
  },
  {
    id: "tokens_total",
    label: "Tokens",
    source: "tokens_total",
    align: "right",
    sortable: true,
    width: 86,
  },
  {
    id: "prompt",
    label: "Prompt",
    source: "prompt",
    align: "right",
    sortable: true,
    width: 80,
    defaultVisible: false,
  },
  {
    id: "completion",
    label: "Completion",
    source: "completion",
    align: "right",
    sortable: true,
    width: 92,
    defaultVisible: false,
  },
  { id: "cost", label: "Cost", source: "cost", align: "right", sortable: true, width: 78 },
  { id: "backend", label: "Backend", source: "backend", sortable: true, width: 92 },
  { id: "model", label: "Model", source: "model", sortable: true, width: 140 },
  { id: "sampling", label: "Sampling", source: "sampling", width: 150 },
  {
    id: "tags",
    label: "Tags",
    source: "tags",
    width: 120,
    defaultVisible: false,
  },
  {
    id: "hash_content",
    label: "hash_content",
    source: "hash_content",
    width: 120,
    defaultVisible: false,
  },
  {
    id: "hash_input",
    label: "hash_input",
    source: "hash_input",
    width: 110,
    defaultVisible: false,
  },
  { id: "hash_prompt", label: "hash_prompt", source: "hash_prompt", width: 110, defaultVisible: false },
  {
    id: "hash_output_schema",
    label: "hash_output_schema",
    source: "hash_output_schema",
    width: 130,
    defaultVisible: false,
  },
  {
    id: "hash_config",
    label: "hash_config",
    source: "hash_config",
    width: 110,
    defaultVisible: false,
  },
  { id: "notes", label: "Notes", source: "notes", width: "1fr" },
];

export function AgentGroupRunsTab() {
  const { hashContent } = useParams<{ hashContent: string }>();
  const group = useAgentGroup(hashContent);
  const navigate = useNavigate();
  const [selected, setSelected] = useState<string[]>([]);
  const [tableVersion, setTableVersion] = useState(0);
  const addToCompare = useUIStore((s) => s.addToCompare);

  if (!hashContent || !group.data) return null;
  const rows = group.data.runs.map((run) => runRow(run, hashContent));

  return (
    <div className="h-full overflow-auto p-4">
      <div className="space-y-3">
        {selected.length >= 1 ? (
          <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-bg-1 px-3 py-2 text-[12px] text-text">
            <span className="font-mono">{selected.length} selected</span>
            {selected.length >= 2 ? (
              <Button
                size="sm"
                variant="primary"
                onClick={() =>
                  navigate(`/experiments?runs=${selected.map(encodeURIComponent).join(",")}`)
                }
              >
                Compare
              </Button>
            ) : null}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                for (const id of selected) addToCompare(id);
              }}
            >
              + add to basket
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setSelected([]);
                setTableVersion((value) => value + 1);
              }}
            >
              Clear
            </Button>
          </div>
        ) : null}
        <RunTable
          key={tableVersion}
          rows={rows}
          columns={columns}
          storageKey={`agent-group-runs:${hashContent}`}
          rowHref={(row) => `/agents/${hashContent}/runs/${row.id}`}
          selectable
          onSelectionChange={setSelected}
          emptyTitle="no invocations"
          emptyDescription="this agent group has not recorded invocations yet"
        />
      </div>
    </div>
  );
}

function runRow(run: RunSummary, hashContent: string): RunRow {
  const tags = [
    ...(run.algorithm_kinds ?? []),
    ...(run.synthetic ? ["synthetic"] : []),
  ].slice(0, 6);
  const totalTokens = run.prompt_tokens + run.completion_tokens;
  return {
    id: run.run_id,
    identity: run.hash_content ?? hashContent,
    state: run.state,
    startedAt: run.started_at,
    endedAt: run.last_event_at,
    durationMs: run.duration_ms,
    fields: {
      prompt: { kind: "num", value: run.prompt_tokens, format: "tokens" },
      completion: { kind: "num", value: run.completion_tokens, format: "tokens" },
      tokens_total: { kind: "num", value: totalTokens > 0 ? totalTokens : null, format: "tokens" },
      cost: { kind: "num", value: run.cost?.cost_usd ?? null, format: "cost" },
      backend: { kind: "text", value: run.backend ?? "-", mono: true },
      model: { kind: "text", value: run.model ?? "-", mono: true },
      sampling: { kind: "text", value: samplingText(run.sampling ?? {}), mono: true },
      tags: { kind: "text", value: tags.length > 0 ? tags.join(", ") : "-" },
      hash_content: { kind: "hash", value: run.hash_content ?? hashContent },
      hash_input: { kind: "hash", value: run.hash_input ?? "-" },
      hash_prompt: { kind: "hash", value: run.hash_prompt ?? run.hash_content ?? hashContent },
      hash_output_schema: { kind: "hash", value: run.hash_output_schema ?? "-" },
      hash_config: { kind: "hash", value: run.hash_config ?? "-" },
      notes: { kind: "markdown", value: truncate(run.notes_markdown ?? "") },
    },
  };
}

function samplingText(sampling: Record<string, unknown>): string {
  const temp = sampling.temperature;
  const topP = sampling.top_p;
  const maxTokens = sampling.max_tokens;
  return [
    temp != null ? `T=${temp}` : null,
    topP != null ? `top_p=${topP}` : null,
    maxTokens != null ? `max_tok=${maxTokens}` : null,
  ]
    .filter(Boolean)
    .join(" ");
}

function truncate(value: string): string {
  const compact = value.replace(/\s+/g, " ").trim();
  return compact.length > 60 ? `${compact.slice(0, 57)}...` : compact;
}
