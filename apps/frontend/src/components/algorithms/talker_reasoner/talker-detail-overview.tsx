import {
  type ScenarioTreeInfo,
  type TalkerTurn,
  arrayValue,
  asRecord,
  currentNodeId,
  decisionTone,
  extractScenarioTree,
  extractTalkerTurns,
  numberValue,
  stringValue,
  walkedPathFromTurns,
} from "@/components/algorithms/talker_reasoner/transcript-view";
import { MarkdownView, PanelCard, PanelGrid, Pill } from "@/components/ui";
import { Button } from "@/components/ui/button";
import { GitBranch, MessagesSquare } from "lucide-react";
import { useSearchParams } from "react-router-dom";

interface TalkerDetailOverviewProps {
  summary?: unknown;
  events?: unknown;
}

export function TalkerDetailOverview({ summary, events }: TalkerDetailOverviewProps) {
  const [, setSearchParams] = useSearchParams();
  const summaryRecord = asRecord(summary);
  const tree = extractScenarioTree(events);
  const turns = extractTalkerTurns(summary, events);
  const current = currentNodeId(summary, tree, turns);
  const processName =
    tree?.name ?? stringValue(firstStartPayload(events)?.process) ?? "TalkerReasoner";
  const maxTurns = numberValue(firstStartPayload(events)?.max_turns);
  const finished = summaryRecord?.state === "ended";

  const openTab = (tab: "tree" | "transcript") => {
    setSearchParams(
      (currentParams) => {
        const next = new URLSearchParams(currentParams);
        next.set("tab", tab);
        return next;
      },
      { replace: false },
    );
  };

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-bg-1 px-3 py-2 text-[12px] text-muted">
        <Pill tone={finished ? "ok" : "live"} pulse={!finished}>
          {finished ? "ended" : "live"}
        </Pill>
        <span className="min-w-0 truncate text-text">process: {processName}</span>
        <span>
          turns {turns.length}
          {maxTurns != null ? ` / ${maxTurns}` : ""}
        </span>
        <span>final node: {current ?? "-"}</span>
        <span>{finished ? "finished" : "in progress"}</span>
      </div>

      <PanelGrid cols={2} gap="md">
        <PanelCard
          title="scenario walk"
          toolbar={
            <Button size="sm" variant="ghost" onClick={() => openTab("tree")}>
              <GitBranch size={13} />
              Open
            </Button>
          }
          bodyMinHeight={220}
        >
          <TreeMini tree={tree} turns={turns} />
        </PanelCard>

        <PanelCard
          title="latest turns"
          toolbar={
            <Button size="sm" variant="ghost" onClick={() => openTab("transcript")}>
              <MessagesSquare size={13} />
              Open
            </Button>
          }
          bodyMinHeight={220}
        >
          <TranscriptMini turns={turns} />
        </PanelCard>
      </PanelGrid>

      <PanelCard title="purpose">
        <MarkdownView value={tree?.purpose || "Scenario purpose unavailable."} />
      </PanelCard>
    </div>
  );
}

function TreeMini({ tree, turns }: { tree: ScenarioTreeInfo | null; turns: TalkerTurn[] }) {
  if (!tree) {
    return (
      <div className="flex h-44 items-center justify-center text-center text-[12px] text-muted">
        tree payload missing
      </div>
    );
  }
  const walked = new Set(walkedPathFromTurns(tree, turns));
  return (
    <div className="grid max-h-48 gap-1 overflow-auto">
      {tree.nodes.slice(0, 8).map((node) => (
        <div
          key={node.id}
          className="flex items-center gap-2 rounded border border-border bg-bg-2 px-2 py-1.5 text-[12px]"
        >
          <span
            className="h-2 w-2 rounded-full"
            style={{ background: walked.has(node.id) ? "var(--qual-7)" : "var(--color-muted)" }}
          />
          <span className="min-w-0 flex-1 truncate font-mono text-text">{node.id}</span>
          {node.terminal ? <span className="text-[10px] text-muted">terminal</span> : null}
        </div>
      ))}
      {tree.nodes.length > 8 ? (
        <div className="text-[11px] text-muted">{tree.nodes.length - 8} more nodes</div>
      ) : null}
    </div>
  );
}

function TranscriptMini({ turns }: { turns: TalkerTurn[] }) {
  if (turns.length === 0) {
    return (
      <div className="flex h-44 items-center justify-center text-center text-[12px] text-muted">
        no turns recorded
      </div>
    );
  }
  return (
    <div className="flex max-h-48 flex-col gap-2 overflow-auto">
      {turns.slice(-3).map((turn) => (
        <div key={turn.turnIndex} className="rounded border border-border bg-bg-2 p-2 text-[12px]">
          <div className="mb-1 flex items-center justify-between gap-2">
            <span className="font-mono text-text">turn {turn.turnIndex + 1}</span>
            <Pill tone={decisionTone(turn.decisionKind)}>{turn.decisionKind}</Pill>
          </div>
          <div className="line-clamp-2 text-muted">
            {turn.userMessage || "user message unavailable"}
          </div>
          <div className="mt-1 line-clamp-2 text-text">
            {turn.assistantMessage || "assistant message unavailable"}
          </div>
        </div>
      ))}
    </div>
  );
}

function firstStartPayload(events: unknown): Record<string, unknown> | null {
  const event = arrayValue(asRecord(events)?.events)
    .map(asRecord)
    .find(
      (candidate): candidate is Record<string, unknown> =>
        candidate?.type === "algo_event" && candidate.kind === "algo_start",
    );
  return asRecord(event?.payload);
}
