import type { AlgorithmColumns } from "@/lib/invocation-columns/types";
import { baseRow, metadataNumber, metricNumber } from "@/lib/invocation-columns/types";

export const beamColumns: AlgorithmColumns = {
  algorithmClass: "Beam",
  defaultGroupBy: "iter",
  columns: [
    { id: "state", label: "State", source: "_state", sortable: true, width: 86 },
    { id: "iter", label: "Iter", source: "iter", sortable: true, align: "right", width: 68 },
    {
      id: "candidate",
      label: "Candidate",
      source: "candidate",
      sortable: true,
      align: "right",
      width: 96,
    },
    {
      id: "score",
      label: "Score",
      source: "score",
      sortable: true,
      align: "right",
      width: 120,
      defaultSort: "desc",
    },
    { id: "latency", label: "Latency", source: "_duration", sortable: true, align: "right", width: 88 },
    { id: "cost", label: "Cost", source: "cost", sortable: true, align: "right", width: 84 },
  ],
  rowMapper: (child) => ({
    ...baseRow(child),
    fields: {
      iter: { kind: "num", value: metadataNumber(child, "iter", "iter_index"), format: "int" },
      candidate: {
        kind: "num",
        value: metadataNumber(child, "candidate", "candidate_index"),
        format: "int",
      },
      score: { kind: "score", value: metricNumber(child, "score") ?? child.algorithm_terminal_score ?? null },
      cost: { kind: "num", value: child.cost?.cost_usd ?? null, format: "cost" },
    },
  }),
};
