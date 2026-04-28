import type { AlgorithmColumns } from "@/lib/invocation-columns/types";
import {
  baseRow,
  metadataNumber,
  metadataString,
  metricNumber,
} from "@/lib/invocation-columns/types";

export const oproColumns: AlgorithmColumns = {
  algorithmClass: "OPRO",
  defaultGroupBy: "iter",
  columns: [
    { id: "state", label: "State", source: "_state", sortable: true, width: 86 },
    { id: "iter", label: "Iter", source: "iter", sortable: true, align: "right", width: 68 },
    { id: "role", label: "Role", source: "role", sortable: true, width: 106 },
    { id: "prompt", label: "Prompt", source: "prompt", width: "1fr" },
    {
      id: "score",
      label: "Score",
      source: "score",
      sortable: true,
      align: "right",
      width: 112,
      defaultSort: "desc",
    },
    { id: "cost", label: "Cost", source: "cost", sortable: true, align: "right", width: 84 },
  ],
  rowMapper: (child, _parent, _index, previous) => ({
    ...baseRow(child),
    fields: {
      iter: { kind: "num", value: metadataNumber(child, "iter", "iter_index"), format: "int" },
      role: { kind: "text", value: metadataString(child, "role", "actor") ?? "candidate", mono: true },
      prompt: {
        kind: "diff",
        value: metadataString(child, "prompt", "text") ?? "—",
        previous: previous ? (metadataString(previous, "prompt", "text") ?? undefined) : undefined,
      },
      score: { kind: "score", value: metricNumber(child, "score") ?? child.algorithm_terminal_score ?? null },
      cost: { kind: "num", value: child.cost?.cost_usd ?? null, format: "cost" },
    },
  }),
};
