import { TabAgentEvents } from "@/components/agent-view/graph/inspector/tab-agent-events";
import { TabAgentInvocations } from "@/components/agent-view/graph/inspector/tab-agent-invocations";
import { TabAgentOverview } from "@/components/agent-view/graph/inspector/tab-agent-overview";
import { TabAgentPrompts } from "@/components/agent-view/graph/inspector/tab-agent-prompts";
import { TabFields } from "@/components/agent-view/graph/inspector/tab-fields";
import { HashRow, type HashKey } from "@/components/ui/hash-row";
import { Eyebrow, HashTag, IconButton, Pill } from "@/components/ui";
import { useAgentMeta } from "@/hooks/use-runs";
import type { IoGraphResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { type GraphInspectorTab, useUIStore } from "@/stores";
import { ExternalLink, X } from "lucide-react";
import { useMemo } from "react";

const EDGE_TABS: Array<{ id: GraphInspectorTab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "invocations", label: "Invocations" },
  { id: "prompts", label: "Prompts" },
  { id: "events", label: "Events" },
];

export function InspectorShell({
  runId,
  ioGraph,
  onClose,
}: {
  runId: string;
  ioGraph: IoGraphResponse;
  onClose: () => void;
}) {
  const selection = useUIStore((s) => s.graphSelection);
  const tab = useUIStore((s) => s.graphInspectorTab);
  const setTab = useUIStore((s) => s.setGraphInspectorTab);

  const meta = useMemo(() => {
    if (!selection) return null;
    if (selection.kind === "edge") {
      const edge = ioGraph.edges.find((e) => e.agent_path === selection.agentPath);
      if (!edge) return null;
      return {
        title: edge.class_name,
        subtitle: edge.agent_path,
        identity: edge.agent_path,
        kind: "edge" as const,
        agentKind: edge.kind,
        agentPath: edge.agent_path,
      };
    }
    if (selection.kind === "node") {
      const node = ioGraph.nodes.find((n) => n.key === selection.nodeKey);
      if (!node) return null;
      return {
        title: node.name,
        subtitle: `${node.fields.length} fields`,
        identity: node.key,
        kind: "node" as const,
        agentPath: null as string | null,
      };
    }
    return null;
  }, [selection, ioGraph]);

  if (!selection || !meta) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-[12px] text-muted-2">
        Select a node or edge to inspect.
      </div>
    );
  }

  const showTabs = meta.kind === "edge";
  const activeTab: GraphInspectorTab = showTabs ? tab : "fields";

  return (
    <div className="flex h-full flex-col">
      <Header
        runId={runId}
        meta={meta}
        onClose={onClose}
      />
      {showTabs ? (
        <div className="flex items-center gap-1 border-b border-border px-3">
          {EDGE_TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={cn(
                "relative h-9 px-3 text-[12px] font-medium transition-colors",
                "after:absolute after:inset-x-3 after:bottom-0 after:h-[2px] after:rounded-t-full after:transition-colors",
                activeTab === t.id
                  ? "text-text after:bg-accent"
                  : "text-muted hover:text-text after:bg-transparent",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      ) : null}
      <div className="min-h-0 flex-1 overflow-auto">
        <Body tab={activeTab} runId={runId} ioGraph={ioGraph} selection={selection} />
      </div>
    </div>
  );
}

function Header({
  runId,
  meta,
  onClose,
}: {
  runId: string;
  meta: {
    title: string;
    subtitle: string;
    identity: string;
    kind: "edge" | "node";
    agentKind?: string;
    agentPath: string | null;
  };
  onClose: () => void;
}) {
  const agentMeta = useAgentMeta(
    meta.kind === "edge" ? runId : null,
    meta.kind === "edge" ? meta.agentPath : null,
  );
  const langfuseUrl = agentMeta.data?.langfuse_search_url ?? null;
  const currentHashes = useMemo(() => {
    return {
      hash_content: agentMeta.data?.hash_content ?? meta.identity,
    } satisfies Partial<Record<HashKey, string | null>>;
  }, [agentMeta.data?.hash_content, meta.identity]);

  return (
    <header className="flex items-start gap-3 border-b border-border px-5 py-4">
      <HashTag hash={meta.identity} dotOnly size="md" />
      <div className="min-w-0 flex-1">
        <Eyebrow>{meta.kind === "edge" ? "agent" : "i/o type"}</Eyebrow>
        <div className="flex items-center gap-2">
          <div className="truncate text-[18px] font-medium leading-tight">{meta.title}</div>
          <HashRow
            variant="compact"
            current={currentHashes}
          />
          {langfuseUrl ? (
            <a
              href={langfuseUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-2 inline-flex items-center gap-1 text-[12px] text-accent transition-colors hover:text-[--color-accent-strong]"
            >
              langfuse <ExternalLink size={11} />
            </a>
          ) : null}
        </div>
        <div className="truncate font-mono text-[11px] text-muted-2">{meta.subtitle}</div>
      </div>
      {meta.kind === "edge" ? (
        <Pill tone="accent">{meta.agentKind}</Pill>
      ) : (
        <Pill>type</Pill>
      )}
      <IconButton aria-label="close inspector" onClick={onClose}>
        <X size={14} />
      </IconButton>
    </header>
  );
}

function Body({
  tab,
  runId,
  ioGraph,
  selection,
}: {
  tab: GraphInspectorTab;
  runId: string;
  ioGraph: IoGraphResponse;
  selection: NonNullable<ReturnType<typeof useUIStore.getState>["graphSelection"]>;
}) {
  if (selection.kind === "node") {
    return <TabFields nodeKey={selection.nodeKey} ioGraph={ioGraph} />;
  }
  const agentPath = selection.kind === "edge" ? selection.agentPath : "";
  switch (tab) {
    case "overview":
      return <TabAgentOverview runId={runId} agentPath={agentPath} />;
    case "invocations":
      return <TabAgentInvocations runId={runId} agentPath={agentPath} />;
    case "prompts":
      return <TabAgentPrompts runId={runId} agentPath={agentPath} />;
    case "events":
      return <TabAgentEvents runId={runId} agentPath={agentPath} />;
    default:
      return null;
  }
}
