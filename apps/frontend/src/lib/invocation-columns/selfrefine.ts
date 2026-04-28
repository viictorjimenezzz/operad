import type { AlgorithmColumns } from "@/lib/invocation-columns/types";
import {
  baseRow,
  diffField,
  langfuseField,
  metadataNumber,
  metadataString,
  metricNumber,
} from "@/lib/invocation-columns/types";

function phaseTone(
  phase: string,
): "ok" | "warn" | "error" | "live" | "accent" | "default" {
  if (phase === "refine" || phase === "reflect") return "accent";
  if (phase === "stop") return "warn";
  return "default";
}

export const selfrefineColumns: AlgorithmColumns = {
  algorithmClass: "SelfRefine",
  defaultGroupBy: "iter",
  columns: [
    { id: "state", label: "State", source: "_state", sortable: true, width: 86 },
    { id: "iter", label: "Iter", source: "iter", sortable: true, align: "right", width: 68 },
    { id: "phase", label: "Phase", source: "phase", sortable: true, width: 104 },
    {
      id: "refineScore",
      label: "Refine score",
      source: "refineScore",
      sortable: true,
      align: "right",
      width: 118,
      defaultSort: "desc",
    },
    { id: "stopReason", label: "Stop reason", source: "stopReason", sortable: true, width: 132 },
    { id: "response", label: "Response", source: "response", width: "1fr" },
    { id: "langfuse", label: "Langfuse", source: "langfuse", width: 92 },
  ],
  rowMapper: (child, _parent, _index, previous) => {
    const phase = metadataString(child, "phase") ?? "refine";
    return {
      ...baseRow(child),
      fields: {
        iter: { kind: "num", value: metadataNumber(child, "iter", "iter_index"), format: "int" },
        phase: { kind: "pill", value: phase, tone: phaseTone(phase) },
        refineScore: { kind: "score", value: metricNumber(child, "score") ?? child.algorithm_terminal_score ?? null },
        stopReason: {
          kind: "text",
          value: metadataString(child, "stop_reason", "reason") ?? "—",
        },
        response: diffField(
          metadataString(child, "response", "text") ?? "—",
          previous ? (metadataString(previous, "response", "text") ?? undefined) : undefined,
        ),
        langfuse: langfuseField(child),
      },
    };
  },
};
