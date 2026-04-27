import { BackendBlock } from "@/components/agent-view/overview/backend-block";
import { ConfigBlock } from "@/components/agent-view/overview/config-block";
import { ExamplesBlock } from "@/components/agent-view/overview/examples-block";
import { IdentityBlock } from "@/components/agent-view/overview/identity-block";
import { ReproducibilityBlock } from "@/components/agent-view/overview/reproducibility-block";
import { CollapsibleSection } from "@/components/ui";
import { useAgentMeta } from "@/hooks/use-runs";
import { RunInvocationsResponse, RunSummary } from "@/lib/types";
import { truncateMiddle } from "@/lib/utils";
import type { ReactNode } from "react";

export interface DefinitionSectionProps {
  dataSummary?: unknown;
  dataInvocations?: unknown;
  sourceSummary?: unknown;
  sourceInvocations?: unknown;
  runId?: string;
}

export function DefinitionSection(props: DefinitionSectionProps) {
  const summary = RunSummary.safeParse(props.dataSummary ?? props.sourceSummary);
  const invocations = RunInvocationsResponse.safeParse(
    props.dataInvocations ?? props.sourceInvocations,
  );
  const run = summary.success ? summary.data : null;
  const rows = invocations.success ? invocations.data.invocations : [];
  const latest = rows[rows.length - 1] ?? null;
  const runId = props.runId ?? run?.run_id;
  const agentPath =
    run?.root_agent_path ?? (invocations.success ? invocations.data.agent_path : null);
  const meta = useAgentMeta(runId ?? null, agentPath ?? null);
  const sampling = meta.data?.config?.sampling as Record<string, unknown> | undefined;
  const temperature = sampling?.temperature ?? null;
  const className = meta.data?.class_name ?? agentPath?.split(".").at(-1) ?? "Agent";
  const backend = latest?.backend ?? meta.data?.config?.backend ?? "backend";
  const model = latest?.model ?? meta.data?.config?.model ?? "model";
  const preview = `${className} · ${backend}/${model} · temp ${temperature ?? "—"}`;

  return (
    <CollapsibleSection id="definition" label="Definition" preview={preview}>
      <div className="divide-y divide-border">
        <DefinitionRow label="Identity">
          <IdentityBlock dataSummary={run} runId={runId} flat />
        </DefinitionRow>
        <DefinitionRow label="Backend & sampling">
          <BackendBlock
            dataSummary={run}
            dataInvocations={invocations.success ? invocations.data : undefined}
            runId={runId}
            flat
          />
        </DefinitionRow>
        <DefinitionRow label="Configuration">
          <ConfigBlock dataSummary={run} runId={runId} flat />
        </DefinitionRow>
        {(meta.data?.examples.length ?? 0) > 0 ? (
          <DefinitionRow label="Examples">
            <ExamplesBlock dataSummary={run} runId={runId} flat />
          </DefinitionRow>
        ) : null}
      </div>
    </CollapsibleSection>
  );
}

export function ReproducibilitySection(props: DefinitionSectionProps) {
  const parsed = RunInvocationsResponse.safeParse(props.dataInvocations ?? props.sourceInvocations);
  const rows = parsed.success ? parsed.data.invocations : [];
  const latest = rows[rows.length - 1] ?? null;
  const previous = rows.length >= 2 ? rows[rows.length - 2] : null;
  const hashes = [
    "hash_content",
    "hash_model",
    "hash_prompt",
    "hash_graph",
    "hash_input",
    "hash_output_schema",
    "hash_config",
  ] as const;
  const present = hashes.filter((key) => Boolean(normalizeHash(latest?.[key])));
  const changed = hashes.filter((key) => {
    const current = normalizeHash(latest?.[key]);
    const prev = normalizeHash(previous?.[key]);
    return Boolean(current && prev && current !== prev);
  });
  const preview = latest?.hash_content
    ? `hash_content ${truncateMiddle(latest.hash_content, 8)} · ${present.length} hashes · ${changed.length} changed since previous`
    : `${present.length} hashes · ${changed.length} changed since previous`;

  return (
    <CollapsibleSection id="reproducibility" label="Reproducibility" preview={preview}>
      <ReproducibilityBlock dataInvocations={parsed.success ? parsed.data : undefined} flat />
    </CollapsibleSection>
  );
}

function DefinitionRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-3 py-4 first:pt-0 last:pb-0 lg:grid-cols-[180px_minmax(0,1fr)]">
      <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-muted-2">
        {label}
      </div>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

function normalizeHash(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed && trimmed !== "—" ? trimmed : null;
}
