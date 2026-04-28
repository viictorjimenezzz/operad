import type { AlgorithmColumns } from "@/lib/invocation-columns/types";
import {
  baseRow,
  diffField,
  langfuseField,
  metadataNumber,
  metadataString,
  metricNumber,
} from "@/lib/invocation-columns/types";

function decisionTone(
  choice: string,
): "ok" | "warn" | "error" | "live" | "accent" | "default" {
  if (choice === "finalize" || choice === "answer") return "ok";
  if (choice === "delegate" || choice === "route") return "accent";
  if (choice === "retry") return "warn";
  if (choice === "reject") return "error";
  return "default";
}

export const talkerReasonerColumns: AlgorithmColumns = {
  algorithmClass: "TalkerReasoner",
  defaultGroupBy: "turn",
  columns: [
    { id: "state", label: "State", source: "_state", sortable: true, width: 86 },
    { id: "turn", label: "Turn", source: "turn", sortable: true, align: "right", width: 68 },
    { id: "router", label: "Router", source: "router", sortable: true, width: 110 },
    { id: "target", label: "Target", source: "target", sortable: true, width: 140 },
    { id: "reason", label: "Reason", source: "reason", width: "1fr" },
    {
      id: "score",
      label: "Score",
      source: "score",
      sortable: true,
      align: "right",
      width: 110,
      defaultSort: "desc",
    },
    { id: "langfuse", label: "Langfuse", source: "langfuse", width: 92 },
  ],
  rowMapper: (child, _parent, _index, previous) => {
    const choice = metadataString(child, "router_choice", "decision") ?? "unknown";
    return {
      ...baseRow(child),
      fields: {
        turn: { kind: "num", value: metadataNumber(child, "turn", "turn_index"), format: "int" },
        router: { kind: "pill", value: choice, tone: decisionTone(choice) },
        target: { kind: "text", value: metadataString(child, "target_node", "to") ?? "—", mono: true },
        reason: diffField(
          metadataString(child, "reason", "text") ?? "—",
          previous ? (metadataString(previous, "reason", "text") ?? undefined) : undefined,
        ),
        score: { kind: "score", value: metricNumber(child, "score") ?? child.algorithm_terminal_score ?? null },
        langfuse: langfuseField(child),
      },
    };
  },
};
