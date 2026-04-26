import { DriftNavigator } from "@/components/agent-view/drawer/views/prompts/drift-navigator";
import { PromptPairDiff } from "@/components/agent-view/drawer/views/prompts/prompt-pair-diff";
import { PromptRenderer } from "@/components/agent-view/drawer/views/prompts/prompt-renderer";
import {
  promptTransitions,
  resolveFocusedTransitionIndex,
  sectionChanges,
  toMarkdownBundle,
  toMarkdownDiff,
} from "@/components/agent-view/drawer/views/prompts/prompt-utils";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Toolbar } from "@/components/ui/toolbar";
import { dashboardApi } from "@/lib/api/dashboard";
import type { AgentEventEnvelope, AgentEventsResponse } from "@/lib/types";
import { truncateMiddle } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

interface PromptDiffViewProps {
  runId: string;
  agentPath: string;
  focus: string | null;
}

type ViewMode = "diff" | "single";
type DiffMode = "side-by-side" | "inline";
type PromptPart = "system" | "user";

export function PromptDiffView({ runId, agentPath, focus }: PromptDiffViewProps) {
  const promptsQuery = useQuery({
    queryKey: ["run", "agent-prompts", runId, agentPath] as const,
    queryFn: () => dashboardApi.agentPrompts(runId, agentPath),
    enabled: runId.length > 0 && agentPath.length > 0,
    staleTime: 30_000,
    retry: false,
  });
  const invocationsQuery = useQuery({
    queryKey: ["run", "agent-invocations", runId, agentPath] as const,
    queryFn: () => dashboardApi.agentInvocations(runId, agentPath),
    enabled: runId.length > 0 && agentPath.length > 0,
    staleTime: 30_000,
    retry: false,
  });
  const metaQuery = useQuery({
    queryKey: ["run", "agent-meta", runId, agentPath] as const,
    queryFn: () => dashboardApi.agentMeta(runId, agentPath),
    enabled: runId.length > 0 && agentPath.length > 0,
    staleTime: 30_000,
    retry: false,
  });
  const eventsQuery = useQuery({
    queryKey: ["run", "agent-events", runId, agentPath] as const,
    queryFn: () => dashboardApi.agentEvents(runId, agentPath, 2000),
    enabled: runId.length > 0 && agentPath.length > 0,
    staleTime: 30_000,
    retry: false,
  });

  const payload = promptsQuery.data;
  const entries = payload?.entries ?? [];
  const renderer = payload?.renderer ?? "xml";

  const transitions = useMemo(() => promptTransitions(entries), [entries]);
  const [viewMode, setViewMode] = useState<ViewMode>("diff");
  const [diffMode, setDiffMode] = useState<DiffMode>("side-by-side");
  const [part, setPart] = useState<PromptPart>("system");
  const [selectedTransitionIndex, setSelectedTransitionIndex] = useState<number>(-1);
  const [singleInvocationId, setSingleInvocationId] = useState<string | null>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied">("idle");

  useEffect(() => {
    if (!entries.length) {
      setSelectedTransitionIndex(-1);
      setSingleInvocationId(null);
      return;
    }
    const index = resolveFocusedTransitionIndex(entries, transitions, focus);
    setSelectedTransitionIndex(index);
    const fallback =
      index >= 0
        ? transitions[index]?.after.invocation_id
        : focus && entries.some((entry) => entry.invocation_id === focus)
          ? focus
          : entries[0]?.invocation_id;
    setSingleInvocationId(fallback ?? null);
  }, [entries, transitions, focus]);

  const selectedTransition =
    selectedTransitionIndex >= 0 ? transitions[selectedTransitionIndex] ?? null : null;
  const selectedSingleEntry =
    entries.find((entry) => entry.invocation_id === singleInvocationId) ?? entries[0] ?? null;

  const diffBefore = selectedTransition?.before ?? null;
  const diffAfter = selectedTransition?.after ?? null;
  const sectionStats = useMemo(() => sectionChanges(entries), [entries]);
  const langfuseUrl = useMemo(() => {
    const afterId = selectedTransition?.after.invocation_id;
    if (afterId) {
      const hit = invocationsQuery.data?.invocations.find((row) => row.id === afterId);
      if (hit?.langfuse_url) return hit.langfuse_url;
    }
    return metaQuery.data?.langfuse_search_url ?? null;
  }, [selectedTransition, invocationsQuery.data, metaQuery.data]);

  const inputByInvocation = useMemo(() => {
    const map = new Map<string, unknown>();
    const invocations = invocationsQuery.data?.invocations ?? [];
    const starts =
      eventsQuery.data?.events
        .filter(isAgentStart)
        .sort((a, b) => a.started_at - b.started_at) ?? [];
    for (let i = 0; i < invocations.length; i += 1) {
      const id = invocations[i]?.id;
      const input = starts[i]?.input;
      if (!id || input === undefined) continue;
      map.set(id, input);
    }
    return map;
  }, [eventsQuery.data, invocationsQuery.data]);

  const activeInput = useMemo(() => {
    if (viewMode === "single") {
      if (!selectedSingleEntry) return null;
      return inputByInvocation.get(selectedSingleEntry.invocation_id) ?? null;
    }
    if (!diffAfter) return null;
    return inputByInvocation.get(diffAfter.invocation_id) ?? null;
  }, [viewMode, selectedSingleEntry, diffAfter, inputByInvocation]);

  if (promptsQuery.isPending) {
    return <EmptyState title="loading prompts" description="fetching rendered prompts" />;
  }
  if (promptsQuery.isError) {
    return <EmptyState title="prompt payload unavailable" description="failed to load prompt entries" />;
  }
  if (entries.length === 0) {
    return <EmptyState title="no prompts yet" description="this agent path has no rendered prompt payload" />;
  }

  const noDrift = transitions.length === 0;

  const onCopyMarkdown = async () => {
    const text =
      viewMode === "single"
        ? selectedSingleEntry
          ? toMarkdownBundle(selectedSingleEntry)
          : ""
        : diffBefore && diffAfter
          ? toMarkdownDiff(diffBefore, diffAfter)
          : "";
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopyState("copied");
      window.setTimeout(() => setCopyState("idle"), 1200);
    } catch {
      setCopyState("idle");
    }
  };

  const onPromotePrompt = async () => {
    const text =
      viewMode === "single"
        ? selectedSingleEntry
          ? [
              "# Promoted Prompt",
              "",
              `agent path: ${agentPath}`,
              `renderer: ${renderer}`,
              "",
              toMarkdownBundle(selectedSingleEntry),
            ].join("\n")
          : ""
        : diffBefore && diffAfter
          ? ["# Promoted Prompt Transition", "", `agent path: ${agentPath}`, "", toMarkdownDiff(diffBefore, diffAfter)].join("\n")
          : "";
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopyState("copied");
      window.setTimeout(() => setCopyState("idle"), 1200);
    } catch {
      setCopyState("idle");
    }
  };

  const openLangfuse = () => {
    if (!langfuseUrl) return;
    window.open(langfuseUrl, "_blank", "noopener,noreferrer");
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <Toolbar className="flex-wrap gap-1">
        <Button
          size="sm"
          variant={viewMode === "diff" ? "primary" : "default"}
          onClick={() => setViewMode("diff")}
          disabled={noDrift}
        >
          diff mode
        </Button>
        <Button
          size="sm"
          variant={viewMode === "single" ? "primary" : "default"}
          onClick={() => setViewMode("single")}
        >
          single mode
        </Button>
        <Button
          size="sm"
          variant={part === "system" ? "primary" : "default"}
          onClick={() => setPart("system")}
        >
          system
        </Button>
        <Button size="sm" variant={part === "user" ? "primary" : "default"} onClick={() => setPart("user")}>
          user
        </Button>
        <Button
          size="sm"
          variant={diffMode === "side-by-side" ? "primary" : "default"}
          onClick={() => setDiffMode("side-by-side")}
          disabled={viewMode !== "diff"}
        >
          side-by-side
        </Button>
        <Button
          size="sm"
          variant={diffMode === "inline" ? "primary" : "default"}
          onClick={() => setDiffMode("inline")}
          disabled={viewMode !== "diff"}
        >
          inline
        </Button>
        <div className="ml-auto flex items-center gap-1">
          <Button size="sm" onClick={onCopyMarkdown}>
            {copyState === "copied" ? "copied" : "copy as markdown"}
          </Button>
          <Button size="sm" onClick={onPromotePrompt}>
            promote this prompt
          </Button>
          <Button size="sm" onClick={openLangfuse} disabled={!langfuseUrl}>
            open in langfuse
          </Button>
        </div>
      </Toolbar>

      <div className="min-h-0 flex-1 overflow-auto p-3">
        <div className="space-y-3">
          <DriftNavigator
            entries={entries}
            transitions={transitions}
            selectedTransitionIndex={selectedTransitionIndex}
            onSelectTransition={(index) => {
              setSelectedTransitionIndex(index);
              const hit = transitions[index]?.after.invocation_id;
              if (hit) setSingleInvocationId(hit);
            }}
          />

          {noDrift ? (
            <div className="rounded border border-dashed border-border p-3 text-[11px] text-muted">
              the prompt has been stable across {entries.length} invocations
            </div>
          ) : null}

          <div className="rounded border border-border bg-bg-1 p-3">
            <div className="mb-2 text-[11px] uppercase tracking-[0.08em] text-muted">
              section drift summary
            </div>
            <div className="flex flex-wrap gap-2 text-[11px]">
              <span className="rounded border border-border bg-bg-2 px-2 py-1">
                role changed {sectionStats.role}x
              </span>
              <span className="rounded border border-border bg-bg-2 px-2 py-1">
                task changed {sectionStats.task}x
              </span>
              <span className="rounded border border-border bg-bg-2 px-2 py-1">
                rules changed {sectionStats.rules}x
              </span>
              <span className="rounded border border-border bg-bg-2 px-2 py-1">
                examples changed {sectionStats.examples}x
              </span>
            </div>
          </div>

          {viewMode === "single" ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-[11px]">
                <span className="text-muted">invocation</span>
                <select
                  className="rounded border border-border bg-bg-2 px-2 py-1 text-[11px]"
                  value={selectedSingleEntry?.invocation_id ?? ""}
                  onChange={(event) => setSingleInvocationId(event.target.value)}
                >
                  {entries.map((entry, index) => (
                    <option key={entry.invocation_id} value={entry.invocation_id}>
                      #{index + 1} · {truncateMiddle(entry.hash_prompt ?? "none", 12)}
                    </option>
                  ))}
                </select>
              </div>
              {selectedSingleEntry ? <PromptRenderer entry={selectedSingleEntry} defaultRenderer={renderer} /> : null}
            </div>
          ) : diffBefore && diffAfter ? (
            <div className="space-y-2">
              <div className="text-[11px] text-muted">
                comparing {diffBefore.invocation_id} → {diffAfter.invocation_id}
              </div>
              <PromptPairDiff
                before={part === "system" ? diffBefore.system : diffBefore.user}
                after={part === "system" ? diffAfter.system : diffAfter.user}
                mode={diffMode}
              />
            </div>
          ) : (
            <EmptyState title="no drift transition selected" />
          )}

          <div className="rounded border border-border bg-bg-1 p-3">
            <div className="mb-2 text-[11px] uppercase tracking-[0.08em] text-muted">
              why did this change?
            </div>
            <p className="m-0 text-[11px] text-muted">
              changes in <code>role</code>, <code>task</code>, <code>rules</code>, and <code>examples</code> usually map to trainable parameters. inspect the trainable parameters panel for causal context.
            </p>
            <a href="#trainable-parameters" className="mt-1 inline-block text-[11px] text-accent">
              jump to trainable parameters
            </a>
          </div>

          <div className="rounded border border-border bg-bg-1 p-3">
            <div className="mb-2 text-[11px] uppercase tracking-[0.08em] text-muted">
              input for this prompt
            </div>
            {activeInput == null ? (
              <p className="m-0 text-[11px] text-muted">input preview unavailable for this invocation</p>
            ) : (
              <pre className="m-0 overflow-auto whitespace-pre-wrap rounded border border-border bg-bg-2 p-2 text-[11px]">
                {JSON.stringify(activeInput, null, 2)}
              </pre>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export const _promptDiff = {
  promptTransitions,
  resolveFocusedTransitionIndex,
  sectionChanges,
  toMarkdownBundle,
  toMarkdownDiff,
};

function isAgentStart(event: AgentEventsResponse["events"][number]): event is AgentEventEnvelope {
  return event.type === "agent_event" && event.kind === "start";
}
