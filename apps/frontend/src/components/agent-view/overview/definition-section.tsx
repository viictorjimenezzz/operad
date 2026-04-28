import { BackendBlock } from "@/components/agent-view/overview/backend-block";
import { ConfigBlock } from "@/components/agent-view/overview/config-block";
import { ExamplesBlock } from "@/components/agent-view/overview/examples-block";
import { Eyebrow, HashRow, MarkdownView } from "@/components/ui";
import type { HashKey } from "@/components/ui/hash-row";
import { useAgentMeta, usePatchRunNotes } from "@/hooks/use-runs";
import { RunInvocationsResponse, RunSummary } from "@/lib/types";
import { useEffect, useState } from "react";

export interface DefinitionPanelProps {
  dataSummary?: unknown;
  dataInvocations?: unknown;
  sourceSummary?: unknown;
  sourceInvocations?: unknown;
  runId?: string;
}

export type ReproducibilitySectionProps = Pick<DefinitionPanelProps, "dataSummary" | "runId">;

type TabId = "role" | "task" | "rules" | "examples" | "config" | "notes";

interface Tab {
  id: TabId;
  label: string;
}

export function DefinitionPanel(props: DefinitionPanelProps) {
  const summary = RunSummary.safeParse(props.dataSummary ?? props.sourceSummary);
  const invocations = RunInvocationsResponse.safeParse(
    props.dataInvocations ?? props.sourceInvocations,
  );
  const run = summary.success ? summary.data : null;
  const runId = props.runId ?? run?.run_id;
  const agentPath =
    run?.root_agent_path ?? (invocations.success ? invocations.data.agent_path : null);
  const meta = useAgentMeta(runId ?? null, agentPath ?? null);
  const [activeTab, setActiveTab] = useState<TabId>("role");
  const [notesValue, setNotesValue] = useState(run?.notes_markdown ?? "");
  const saveNotes = usePatchRunNotes();

  useEffect(() => {
    setNotesValue(run?.notes_markdown ?? "");
  }, [run?.notes_markdown]);

  const role = meta.data?.role?.trim() ?? null;
  const task = meta.data?.task?.trim() ?? null;
  const rules = meta.data?.rules ?? [];
  const examples = meta.data?.examples ?? [];

  const tabs: Tab[] = [
    { id: "role", label: "role" },
    { id: "task", label: "task" },
    ...(rules.length > 0 ? [{ id: "rules" as TabId, label: `rules (${rules.length})` }] : []),
    ...(examples.length > 0
      ? [{ id: "examples" as TabId, label: `examples (${examples.length})` }]
      : []),
    { id: "config", label: "config" },
    { id: "notes", label: "notes" },
  ];

  const visibleIds = tabs.map((t) => t.id);
  const current: TabId = visibleIds.includes(activeTab) ? activeTab : (tabs[0]?.id ?? "role");

  return (
    <section className="border-t border-border pt-4">
      <div className="flex border-b border-border">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`px-3 py-1.5 text-[12px] transition-colors ${
              current === tab.id
                ? "-mb-px border-b-2 border-accent font-medium text-text"
                : "text-muted hover:text-text"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="pt-3">
        {current === "role" &&
          (role ? (
            <MarkdownView value={role} />
          ) : (
            <span className="text-[12px] text-muted-2">no role defined</span>
          ))}
        {current === "task" &&
          (task ? (
            <MarkdownView value={task} />
          ) : (
            <span className="text-[12px] text-muted-2">no task defined</span>
          ))}
        {current === "rules" && rules.length > 0 && (
          <ol className="ml-4 list-decimal space-y-1 text-[13px] text-text marker:text-muted-2">
            {rules.map((rule, i) => (
              <li key={i}>{rule}</li>
            ))}
          </ol>
        )}
        {current === "examples" && <ExamplesBlock dataSummary={run} runId={runId} flat />}
        {current === "config" && (
          <div className="space-y-4">
            <BackendBlock
              dataSummary={run}
              dataInvocations={invocations.success ? invocations.data : undefined}
              runId={runId}
              flat
            />
            <ConfigBlock dataSummary={run} runId={runId} flat />
          </div>
        )}
        {current === "notes" && (
          <MarkdownView
            value={notesValue}
            {...(runId
              ? {
                  onSave: async (next: string) => {
                    const saved = await saveNotes.mutateAsync({ runId, markdown: next });
                    setNotesValue(saved.notes_markdown);
                  },
                }
              : {})}
          />
        )}
      </div>
    </section>
  );
}

export function DefinitionSection(props: DefinitionPanelProps) {
  return <DefinitionPanel {...props} />;
}

export function ReproducibilitySection({ dataSummary }: ReproducibilitySectionProps) {
  const summary = RunSummary.safeParse(dataSummary);
  if (!summary.success) return null;

  const current: Partial<Record<HashKey, string | null>> = {
    hash_content: summary.data.hash_content ?? null,
    hash_model: summary.data.hash_model ?? null,
    hash_prompt: summary.data.hash_prompt ?? null,
    hash_input: summary.data.hash_input ?? null,
    hash_output_schema: summary.data.hash_output_schema ?? null,
    hash_graph: summary.data.hash_graph ?? null,
    hash_config: summary.data.hash_config ?? null,
  };

  return (
    <section className="space-y-2 border-t border-border pt-4">
      <Eyebrow>reproducibility</Eyebrow>
      <HashRow current={current} />
    </section>
  );
}
