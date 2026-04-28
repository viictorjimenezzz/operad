import { MarkdownView, EmptyState } from "@/components/ui";
import { hashColor } from "@/lib/hash-color";

interface TalkerTranscriptTabProps {
  dataSummary?: unknown;
  dataEvents?: unknown;
}

export interface TalkerTurnRow {
  turn: number;
  routerChoice: string;
  routerConfidence: number | null;
  fromNodeId: string;
  toNodeId: string;
  userMessage: string;
  reasonerPath: string;
  reasonerOutput: string;
  talkerPath: string;
  talkerOutput: string;
  finalResponsePreview: string;
  langfuseUrl: string | null;
}

export function TalkerTranscriptTab({ dataSummary, dataEvents }: TalkerTranscriptTabProps) {
  const turns = buildTurnRows(dataSummary, dataEvents);

  if (turns.length === 0) {
    return (
      <EmptyState
        title="no transcript turns yet"
        description="TalkerReasoner speak events will populate the conversation transcript"
      />
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mb-3 flex items-center justify-between border-b border-border pb-2">
        <div className="text-[10px] uppercase tracking-[0.08em] text-muted-2">transcript</div>
        <div className="font-mono text-[11px] text-muted">{turns.length} turns</div>
      </div>

      <div className="flex flex-col gap-5">
        {turns.map((turn) => {
          const outputs = [
            turn.reasonerOutput
              ? { kind: "reasoner", path: turn.reasonerPath, text: turn.reasonerOutput }
              : null,
            turn.talkerOutput
              ? { kind: "talker", path: turn.talkerPath, text: turn.talkerOutput }
              : null,
          ].filter((item): item is { kind: "reasoner" | "talker"; path: string; text: string } =>
            item !== null,
          );

          return (
            <section key={turn.turn} className="flex flex-col gap-2" id={`talker-turn-${turn.turn}`}>
              <div className="flex items-start justify-end gap-2">
                <div className="max-w-[80%] rounded-lg border border-[--color-accent-dim] bg-[--color-accent-dim]/20 px-3 py-2 text-[13px] text-text">
                  <MarkdownView value={turn.userMessage || "_user message unavailable_"} />
                </div>
                <UserIcon />
              </div>

              {outputs.length > 0 ? (
                outputs.map((output) => (
                  <div key={`${turn.turn}-${output.kind}`} className="flex items-start gap-2">
                    <AgentIdentity path={output.path || output.kind} label={output.kind} />
                    <div className="max-w-[80%] rounded-lg border border-border bg-bg-2 px-3 py-2 text-[13px] text-text">
                      <MarkdownView value={output.text} />
                    </div>
                  </div>
                ))
              ) : (
                <div className="flex items-start gap-2">
                  <AgentIdentity path={turn.routerChoice} label="agent" />
                  <div className="max-w-[80%] rounded-lg border border-border bg-bg-2 px-3 py-2 text-[13px] text-muted">
                    no agent output recorded for this turn
                  </div>
                </div>
              )}
            </section>
          );
        })}
      </div>
    </div>
  );
}

function UserIcon() {
  return (
    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-[--color-accent-dim] bg-bg-1 text-[10px] font-semibold text-[--color-accent]">
      U
    </div>
  );
}

function AgentIdentity({ path, label }: { path: string; label: string }) {
  return (
    <div className="w-28 shrink-0 pt-0.5">
      <div className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.08em] text-muted-2">
        <span className="h-1.5 w-1.5 rounded-full" style={{ background: hashColor(path) }} />
        {label}
      </div>
      <div className="truncate font-mono text-[11px] text-muted" title={path}>
        {path}
      </div>
    </div>
  );
}

export function buildTurnRows(summary: unknown, events: unknown): TalkerTurnRow[] {
  const rows = speakRows(summary, events);
  const agentRows = agentOutputs(events);

  return rows.map((row, index) => {
    const agent = agentRows[index] ?? EMPTY_AGENT_OUTPUT;
    const routerChoice =
      str(row.router_choice) ?? str(row.decision_kind) ?? inferChoice(str(row.to_node_id)) ?? "unknown";
    const talkerOutput = str(row.assistant_message) ?? agent.talkerOutput ?? "";

    return {
      turn: (num(row.iter_index) ?? index) + 1,
      routerChoice,
      routerConfidence:
        num(row.router_confidence) ?? num(row.decision_confidence) ?? num(row.confidence) ?? null,
      fromNodeId: str(row.from_node_id) ?? "",
      toNodeId: str(row.to_node_id) ?? "",
      userMessage: str(row.user_message) ?? agent.userMessage ?? "",
      reasonerPath: agent.reasonerPath,
      reasonerOutput: str(row.reasoner_output) ?? agent.reasonerOutput ?? "",
      talkerPath: agent.talkerPath,
      talkerOutput,
      finalResponsePreview: str(row.final_response_preview) ?? talkerOutput,
      langfuseUrl: str(row.langfuse_url) ?? agent.langfuseUrl ?? null,
    };
  });
}

const EMPTY_AGENT_OUTPUT = {
  userMessage: "",
  reasonerPath: "Reasoner",
  reasonerOutput: "",
  talkerPath: "Talker",
  talkerOutput: "",
  langfuseUrl: null as string | null,
};

function speakRows(summary: unknown, events: unknown): Record<string, unknown>[] {
  const eventSpeak = eventRecords(events)
    .filter((event) => event.type === "algo_event" && event.kind === "iteration")
    .map((event) => rec(event.payload))
    .filter((payload): payload is Record<string, unknown> => payload?.phase === "speak")
    .sort((a, b) => (num(a.iter_index) ?? 0) - (num(b.iter_index) ?? 0));

  if (eventSpeak.length > 0) return eventSpeak;

  return arr(rec(summary)?.iterations)
    .map(rec)
    .filter((row): row is Record<string, unknown> => row?.phase === "speak")
    .map((row) => ({ ...(rec(row.metadata) ?? {}), iter_index: row.iter_index, phase: row.phase }));
}

function agentOutputs(events: unknown): Array<{
  userMessage: string;
  reasonerPath: string;
  reasonerOutput: string;
  talkerPath: string;
  talkerOutput: string;
  langfuseUrl: string | null;
}> {
  const rows: Array<{
    userMessage: string;
    reasonerPath: string;
    reasonerOutput: string;
    talkerPath: string;
    talkerOutput: string;
    langfuseUrl: string | null;
  }> = [];

  const reasoner: Array<{ path: string; text: string; langfuseUrl: string | null }> = [];
  const talker: Array<{ path: string; text: string; langfuseUrl: string | null }> = [];
  const userMessages: string[] = [];

  for (const event of eventRecords(events)) {
    if (event.type !== "agent_event") continue;

    const input = rec(event.input);
    const userMessage = str(input?.user_message);
    if (userMessage && userMessages.at(-1) !== userMessage) userMessages.push(userMessage);

    if (event.kind !== "end") continue;

    const path = str(event.agent_path) ?? "";
    const text = outputText(event.output) ?? "";
    const langfuseUrl = str(event.langfuse_url) ?? null;

    if (isReasoner(path)) reasoner.push({ path: path || "Reasoner", text, langfuseUrl });
    if (isTalker(path)) talker.push({ path: path || "Talker", text, langfuseUrl });
  }

  const size = Math.max(userMessages.length, reasoner.length, talker.length);
  for (let i = 0; i < size; i += 1) {
    const reasonerRow = reasoner[i];
    const talkerRow = talker[i];
    rows.push({
      userMessage: userMessages[i] ?? "",
      reasonerPath: reasonerRow?.path ?? "Reasoner",
      reasonerOutput: reasonerRow?.text ?? "",
      talkerPath: talkerRow?.path ?? "Talker",
      talkerOutput: talkerRow?.text ?? "",
      langfuseUrl: reasonerRow?.langfuseUrl ?? talkerRow?.langfuseUrl ?? null,
    });
  }

  return rows;
}

function outputText(value: unknown): string | null {
  if (typeof value === "string") return value;
  const output = rec(value);
  if (!output) return null;
  const response = rec(output.response);
  return (
    str(output.text) ??
    str(output.message) ??
    str(output.content) ??
    str(response?.text) ??
    str(response?.message) ??
    str(response?.content)
  );
}

function inferChoice(toNodeId: string | null): string | null {
  if (!toNodeId) return null;
  const node = toNodeId.toLowerCase();
  if (node.includes("reasoner") || node.includes("navigate")) return "reasoner";
  if (node.includes("talker") || node.includes("assistant")) return "talker";
  return null;
}

function isReasoner(path: string): boolean {
  return path.includes("Reasoner") || path.includes("Navigator");
}

function isTalker(path: string): boolean {
  return path.includes("Talker") || path.includes("Assistant");
}

function eventRecords(events: unknown): Record<string, unknown>[] {
  return arr(rec(events)?.events)
    .map(rec)
    .filter((event): event is Record<string, unknown> => event != null);
}

function rec(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function arr(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function str(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
