import type { AlgorithmColumns } from "@/lib/invocation-columns/types";
import {
  baseRow,
  langfuseField,
  metadataNumber,
  metadataString,
  metricNumber,
} from "@/lib/invocation-columns/types";

export const evogradientColumns: AlgorithmColumns = {
  algorithmClass: "EvoGradient",
  defaultGroupBy: "gen",
  columns: [
    { id: "state", label: "State", source: "_state", sortable: true, width: 86 },
    { id: "gen", label: "Gen", source: "gen", sortable: true, align: "right", width: 68 },
    {
      id: "individual",
      label: "Individual",
      source: "individual",
      sortable: true,
      width: 104,
    },
    { id: "operator", label: "Operator", source: "operator", sortable: true, width: 120 },
    {
      id: "score",
      label: "Score",
      source: "score",
      sortable: true,
      align: "right",
      width: 112,
      defaultSort: "desc",
    },
    {
      id: "delta",
      label: "Delta",
      source: "delta",
      sortable: true,
      align: "right",
      width: 100,
    },
    { id: "langfuse", label: "Langfuse", source: "langfuse", width: 92 },
  ],
  rowMapper: (child) => ({
    ...baseRow(child),
    fields: {
      gen: { kind: "num", value: metadataNumber(child, "gen", "gen_index"), format: "int" },
      individual: {
        kind: "text",
        value:
          metadataString(child, "individual_id", "individual", "candidate_id") ??
          child.run_id.slice(0, 8),
        mono: true,
      },
      operator: {
        kind: "text",
        value: metadataString(child, "operator", "operator_kind") ?? "unknown",
      },
      score: { kind: "score", value: metricNumber(child, "score") ?? child.algorithm_terminal_score ?? null },
      delta: { kind: "num", value: metadataNumber(child, "delta", "score_delta"), format: "score" },
      langfuse: langfuseField(child),
    },
  }),
};
