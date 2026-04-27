import { MarkdownView } from "@/components/ui";
import type { PillTone } from "@/components/ui/pill";
import { Pill } from "@/components/ui/pill";
import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";

type DecisionTone = Exclude<PillTone, "algo">;

export interface ScenarioNodeInfo {
  id: string;
  title: string;
  prompt: string;
  terminal: boolean;
  parent_id: string | null;
}

export interface ScenarioTreeInfo {
  name: string;
  purpose: string;
  rootId: string;
  nodes: ScenarioNodeInfo[];
}

export interface TalkerTurn {
  turnIndex: number;
  userMessage: string;
  assistantMessage: string;
  decisionKind: string;
  fromNodeId: string;
  toNodeId: string;
}

interface TranscriptViewProps {
  summary?: unknown;
  events?: unknown;
}

export function TranscriptView({ summary, events }: TranscriptViewProps) {
  const [searchParams] = useSearchParams();
  const pinnedTurn = searchParams.get("turn");
  const turns = extractTalkerTurns(summary, events);
  const tree = extractScenarioTree(events);

  useEffect(() => {
    if (!pinnedTurn) return;
    const id = window.setTimeout(() => {
      document.getElementById(`talker-turn-${pinnedTurn}`)?.scrollIntoView({
        block: "center",
        behavior: "smooth",
      });
    }, 80);
    return () => window.clearTimeout(id);
  }, [pinnedTurn]);

  if (turns.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center">
        <div>
          <div className="text-sm font-medium text-text">no transcript turns yet</div>
          <div className="mt-1 text-xs text-muted">
            TalkerReasoner speak events will populate the conversation transcript
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mb-4 flex items-center justify-between gap-3 border-b border-border pb-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.08em] text-muted-2">topic</div>
          <div className="text-sm font-medium text-text">{tree?.name ?? "TalkerReasoner"}</div>
        </div>
        <div className="font-mono text-[12px] text-muted">{turns.length} turns</div>
      </div>

      <div className="flex flex-col gap-4">
        {turns.map((turn) => {
          const displayTurn = turn.turnIndex + 1;
          return (
            <div key={turn.turnIndex} id={`talker-turn-${displayTurn}`} className="grid gap-2">
              <div className="flex items-start gap-3">
                <SpeakerLabel label="user" turn={displayTurn} />
                <MessageBubble
                  align="left"
                  text={turn.userMessage || "_user message unavailable_"}
                />
                <DecisionPill turn={turn} />
              </div>
              <div className="flex items-start gap-3">
                <SpeakerLabel label="assist" turn={displayTurn} />
                <MessageBubble
                  align="right"
                  text={turn.assistantMessage || "_assistant message unavailable_"}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function extractScenarioTree(events: unknown): ScenarioTreeInfo | null {
  const start = eventRecords(events).find(
    (event) => event.type === "algo_event" && event.kind === "algo_start",
  );
  const tree = asRecord(asRecord(start?.payload)?.tree);
  if (!tree) return null;
  const nodes = arrayValue(tree.nodes).flatMap((item) => {
    const node = asRecord(item);
    const id = stringValue(node?.id);
    const title = stringValue(node?.title);
    if (!id || !title) return [];
    return [
      {
        id,
        title,
        prompt: stringValue(node?.prompt) ?? "",
        terminal: Boolean(node?.terminal),
        parent_id: stringValue(node?.parent_id),
      },
    ];
  });
  const name = stringValue(tree.name);
  const rootId = stringValue(tree.rootId);
  if (!name || !rootId || nodes.length === 0) return null;
  return {
    name,
    purpose: stringValue(tree.purpose) ?? "",
    rootId,
    nodes,
  };
}

export function extractTalkerTurns(summary: unknown, events: unknown): TalkerTurn[] {
  const speakEvents = eventRecords(events)
    .filter((event) => event.type === "algo_event" && event.kind === "iteration")
    .map((event) => asRecord(event.payload))
    .filter((payload): payload is Record<string, unknown> => payload?.phase === "speak")
    .sort((a, b) => (numberValue(a.iter_index) ?? 0) - (numberValue(b.iter_index) ?? 0));

  const summarySpeak: Record<string, unknown>[] = arrayValue(asRecord(summary)?.iterations)
    .map(asRecord)
    .filter((row): row is Record<string, unknown> => row?.phase === "speak")
    .map((row) => ({
      ...(asRecord(row.metadata) ?? {}),
      iter_index: row.iter_index,
      phase: row.phase,
    }));

  const source: Record<string, unknown>[] = speakEvents.length > 0 ? speakEvents : summarySpeak;
  const userMessages = extractUserMessages(events);
  const assistantMessages = extractAssistantMessages(events);

  return source.map((payload, index) => {
    const turnIndex = numberValue(payload.iter_index) ?? index;
    return {
      turnIndex,
      userMessage: stringValue(payload.user_message) ?? userMessages[index] ?? "",
      assistantMessage: stringValue(payload.assistant_message) ?? assistantMessages[index] ?? "",
      decisionKind: stringValue(payload.decision_kind) ?? "unknown",
      fromNodeId: stringValue(payload.from_node_id) ?? "",
      toNodeId: stringValue(payload.to_node_id) ?? "",
    };
  });
}

export function walkedPathFromTurns(tree: ScenarioTreeInfo | null, turns: TalkerTurn[]): string[] {
  if (!tree) return [];
  const out = [tree.rootId];
  for (const turn of turns) {
    if (turn.toNodeId && out[out.length - 1] !== turn.toNodeId) out.push(turn.toNodeId);
  }
  return out;
}

export function currentNodeId(
  summary: unknown,
  tree: ScenarioTreeInfo | null,
  turns: TalkerTurn[],
): string | null {
  const summaryRecord = asRecord(summary);
  if (summaryRecord?.state === "running") {
    return turns.at(-1)?.toNodeId || tree?.rootId || null;
  }
  return turns.at(-1)?.toNodeId || tree?.rootId || null;
}

export function decisionTone(kind: string): DecisionTone {
  switch (kind) {
    case "advance":
      return "ok";
    case "branch":
      return "accent";
    case "finish":
      return "warn";
    case "stay":
      return "default";
    default:
      return "default";
  }
}

export function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function arrayValue(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

export function stringValue(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

export function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function SpeakerLabel({ label, turn }: { label: string; turn: number }) {
  return (
    <div className="w-16 shrink-0 pt-2 text-right">
      <div className="text-[10px] uppercase tracking-[0.08em] text-muted-2">{label}</div>
      <div className="font-mono text-[10px] text-muted">turn {turn}</div>
    </div>
  );
}

function MessageBubble({ text, align }: { text: string; align: "left" | "right" }) {
  return (
    <div
      className={
        align === "left"
          ? "min-w-0 flex-1 rounded-lg border border-border bg-bg-2 px-3 py-2"
          : "min-w-0 flex-1 rounded-lg border border-[--color-accent-dim] bg-[--color-accent-dim]/20 px-3 py-2"
      }
    >
      <MarkdownView value={text} />
    </div>
  );
}

function DecisionPill({ turn }: { turn: TalkerTurn }) {
  return (
    <div className="hidden w-48 shrink-0 pt-2 text-right md:block">
      <Pill tone={decisionTone(turn.decisionKind)}>{turn.decisionKind}</Pill>
      <div className="mt-1 truncate font-mono text-[10px] text-muted" title={turn.toNodeId}>
        {turn.fromNodeId || "-"} -&gt; {turn.toNodeId || "-"}
      </div>
    </div>
  );
}

function eventRecords(events: unknown): Record<string, unknown>[] {
  return arrayValue(asRecord(events)?.events)
    .map(asRecord)
    .filter((event): event is Record<string, unknown> => event != null);
}

function extractUserMessages(events: unknown): string[] {
  const seen = new Set<string>();
  const messages: string[] = [];
  for (const event of eventRecords(events)) {
    if (event.type !== "agent_event") continue;
    const input = asRecord(event.input);
    const message = stringValue(input?.user_message);
    if (!message || seen.has(message)) continue;
    seen.add(message);
    messages.push(message);
  }
  return messages;
}

function extractAssistantMessages(events: unknown): string[] {
  return eventRecords(events)
    .filter((event) => event.type === "agent_event" && event.kind === "end")
    .filter((event) => {
      const path = stringValue(event.agent_path) ?? "";
      return path.includes("Assistant") || path.includes("Talker");
    })
    .map((event) => extractText(event.output))
    .filter((text): text is string => text != null);
}

function extractText(value: unknown): string | null {
  if (typeof value === "string") return value;
  const record = asRecord(value);
  if (!record) return null;
  const response = asRecord(record.response);
  return (
    stringValue(record.text) ??
    stringValue(record.message) ??
    stringValue(record.content) ??
    stringValue(response?.text) ??
    stringValue(response?.message) ??
    stringValue(response?.content)
  );
}
