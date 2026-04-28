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
  if (phase === "plan") return "accent";
  if (phase === "retrieve" || phase === "search") return "live";
  if (phase === "synthesize") return "ok";
  if (phase === "reject") return "error";
  return "default";
}

export const autoResearcherColumns: AlgorithmColumns = {
  algorithmClass: "AutoResearcher",
  defaultGroupBy: "attempt",
  columns: [
    { id: "state", label: "State", source: "_state", sortable: true, width: 86 },
    { id: "attempt", label: "Attempt", source: "attempt", sortable: true, align: "right", width: 82 },
    { id: "phase", label: "Phase", source: "phase", sortable: true, width: 104 },
    { id: "query", label: "Query", source: "query", width: "1fr" },
    {
      id: "score",
      label: "Score",
      source: "score",
      sortable: true,
      align: "right",
      width: 110,
      defaultSort: "desc",
    },
    { id: "cost", label: "Cost", source: "cost", sortable: true, align: "right", width: 84 },
    { id: "langfuse", label: "Langfuse", source: "langfuse", width: 92 },
  ],
  rowMapper: (child, _parent, _index, previous) => {
    const phase = metadataString(child, "phase") ?? "attempt";
    return {
      ...baseRow(child),
      fields: {
        attempt: {
          kind: "num",
          value: metadataNumber(child, "attempt", "attempt_index", "iter_index"),
          format: "int",
        },
        phase: { kind: "pill", value: phase, tone: phaseTone(phase) },
        query: diffField(
          metadataString(child, "query", "text") ?? "—",
          previous ? (metadataString(previous, "query", "text") ?? undefined) : undefined,
        ),
        score: { kind: "score", value: metricNumber(child, "score") ?? child.algorithm_terminal_score ?? null },
        cost: { kind: "num", value: child.cost?.cost_usd ?? null, format: "cost" },
        langfuse: langfuseField(child),
      },
    };
  },
};
