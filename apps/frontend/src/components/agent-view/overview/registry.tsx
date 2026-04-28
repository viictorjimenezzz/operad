import { BackendBlock } from "@/components/agent-view/overview/backend-block";
import { ConfigBlock } from "@/components/agent-view/overview/config-block";
import { DefinitionPanel } from "@/components/agent-view/overview/definition-section";
import { DriftBlock } from "@/components/agent-view/overview/drift-block";
import { ExamplesBlock } from "@/components/agent-view/overview/examples-block";
import { IdentityBlock } from "@/components/agent-view/overview/identity-block";
import { InvocationsBanner } from "@/components/agent-view/overview/invocations-banner";
import { InvocationsList } from "@/components/agent-view/overview/invocations-list";
import { IOHero } from "@/components/agent-view/overview/io-hero";
import { MetricsValueTable } from "@/components/agent-view/overview/metrics-value-table";
import { NotesSection } from "@/components/agent-view/overview/notes-section";
import { ReproducibilityBlock } from "@/components/agent-view/overview/reproducibility-block";
import { ActivityStrip } from "@/components/agent-view/overview/run-status-strip";
import { TrainableParamsBlock } from "@/components/agent-view/overview/trainable-params-block";
import type { ComponentRegistry } from "@json-render/react";

function defined<T extends Record<string, unknown>>(
  obj: T,
): { [K in keyof T]?: Exclude<T[K], undefined> } {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(obj)) {
    if (v !== undefined) out[k] = v;
  }
  return out as { [K in keyof T]?: Exclude<T[K], undefined> };
}

function strProp(p: Record<string, unknown>, key: string): string | undefined {
  const v = p[key];
  return typeof v === "string" ? v : undefined;
}

export const overviewRegistry: ComponentRegistry = {
  IdentityBlock: ({ element }) => {
    const p = element.props as Record<string, unknown>;
    return (
      <IdentityBlock
        dataSummary={p.dataSummary}
        flat={Boolean(p.flat)}
        {...defined({ runId: strProp(p, "runId") })}
      />
    );
  },
  InvocationsBanner: ({ element }) => {
    const p = element.props as Record<string, unknown>;
    return (
      <InvocationsBanner
        dataSummary={p.dataSummary}
        dataInvocations={p.dataInvocations}
        {...defined({ runId: strProp(p, "runId") })}
      />
    );
  },
  InvocationsList: ({ element }) => {
    const p = element.props as Record<string, unknown>;
    return (
      <InvocationsList
        dataSummary={p.dataSummary}
        dataInvocations={p.dataInvocations}
        {...defined({ runId: strProp(p, "runId") })}
        skipLatest={Boolean(p.skipLatest)}
        hideIfEmpty={p.hideIfEmpty !== false}
        density={(p.density as "compact" | "full" | undefined) ?? "compact"}
      />
    );
  },
  ReproducibilityBlock: ({ element }) => {
    const p = element.props as Record<string, unknown>;
    return <ReproducibilityBlock dataInvocations={p.dataInvocations} flat={Boolean(p.flat)} />;
  },
  BackendBlock: ({ element }) => {
    const p = element.props as Record<string, unknown>;
    return (
      <BackendBlock
        dataSummary={p.dataSummary}
        dataInvocations={p.dataInvocations}
        flat={Boolean(p.flat)}
        {...defined({ runId: strProp(p, "runId") })}
      />
    );
  },
  ConfigBlock: ({ element }) => {
    const p = element.props as Record<string, unknown>;
    return (
      <ConfigBlock
        dataSummary={p.dataSummary}
        flat={Boolean(p.flat)}
        {...defined({ runId: strProp(p, "runId") })}
      />
    );
  },
  ExamplesBlock: ({ element }) => {
    const p = element.props as Record<string, unknown>;
    return (
      <ExamplesBlock
        dataSummary={p.dataSummary}
        flat={Boolean(p.flat)}
        {...defined({ runId: strProp(p, "runId") })}
      />
    );
  },
  DriftBlock: ({ element }) => {
    const p = element.props as Record<string, unknown>;
    return (
      <DriftBlock
        dataInvocations={p.dataInvocations}
        {...defined({ runId: strProp(p, "runId") })}
      />
    );
  },
  ActivityStrip: ({ element }) => {
    const p = element.props as Record<string, unknown>;
    return (
      <ActivityStrip
        dataSummary={p.dataSummary ?? p.sourceSummary}
        dataInvocations={p.dataInvocations ?? p.sourceInvocations}
        {...defined({ runId: strProp(p, "runId") })}
      />
    );
  },
  IOHero: ({ element }) => {
    const p = element.props as Record<string, unknown>;
    return (
      <IOHero
        dataInvocations={p.dataInvocations ?? p.sourceInvocations}
        {...defined({ runId: strProp(p, "runId") })}
      />
    );
  },
  NotesSection: ({ element }) => {
    const p = element.props as Record<string, unknown>;
    return (
      <NotesSection dataSummary={p.dataSummary} {...defined({ runId: strProp(p, "runId") })} />
    );
  },
  DefinitionPanel: ({ element }) => {
    const p = element.props as Record<string, unknown>;
    return (
      <DefinitionPanel
        dataSummary={p.dataSummary ?? p.sourceSummary}
        dataInvocations={p.dataInvocations ?? p.sourceInvocations}
        {...defined({ runId: strProp(p, "runId") })}
      />
    );
  },
  MetricsValueTable: ({ element }) => {
    const p = element.props as Record<string, unknown>;
    return (
      <MetricsValueTable
        dataSummary={p.dataSummary}
        sourceGroupMetrics={p.dataGroupMetrics}
        {...defined({
          runId: strProp(p, "runId"),
          hashContent: strProp(p, "hashContent"),
        })}
      />
    );
  },
  TrainableParamsBlock: ({ element }) => {
    const p = element.props as Record<string, unknown>;
    return (
      <TrainableParamsBlock
        dataSummary={p.dataSummary}
        {...defined({ runId: strProp(p, "runId") })}
      />
    );
  },
};
