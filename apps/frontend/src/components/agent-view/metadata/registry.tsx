import { AgentMetadataPanel } from "@/components/agent-view/metadata/agent-metadata-panel";
import { HashChip } from "@/components/agent-view/metadata/hash-chip";
import { InvocationsTable } from "@/components/agent-view/metadata/invocations-table";
import { ScriptOriginChip } from "@/components/agent-view/metadata/script-origin-chip";
import type { ComponentRegistry } from "@json-render/react";
import { z } from "zod";

export const metadataDefinitions = {
  AgentMetadataPanel: {
    props: z.object({
      dataSummary: z.unknown().optional(),
      dataInvocations: z.unknown().optional(),
    }),
  },
  InvocationsTable: {
    props: z.object({
      dataSummary: z.unknown().optional(),
      dataInvocations: z.unknown().optional(),
    }),
  },
  HashChip: {
    props: z.object({ dataHash: z.string().nullable().optional() }),
  },
  ScriptOriginChip: {
    props: z.object({ dataScript: z.string().nullable().optional() }),
  },
} as const;

export const metadataComponents: ComponentRegistry = {
  AgentMetadataPanel: ({ element }) => {
    const p = element.props as { dataSummary?: unknown; dataInvocations?: unknown };
    return <AgentMetadataPanel summary={p.dataSummary} invocations={p.dataInvocations} />;
  },
  InvocationsTable: ({ element }) => {
    const p = element.props as { dataSummary?: unknown; dataInvocations?: unknown };
    return <InvocationsTable summary={p.dataSummary} invocations={p.dataInvocations} />;
  },
  HashChip: ({ element }) => (
    <HashChip hash={(element.props as { dataHash?: string | null }).dataHash} />
  ),
  ScriptOriginChip: ({ element }) => (
    <ScriptOriginChip script={(element.props as { dataScript?: string | null }).dataScript} />
  ),
};
