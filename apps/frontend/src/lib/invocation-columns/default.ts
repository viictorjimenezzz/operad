import type { AlgorithmColumns } from "@/lib/invocation-columns/types";
import { baseRow, metricNumber } from "@/lib/invocation-columns/types";

export const defaultColumns: AlgorithmColumns = {
  algorithmClass: "__default__",
  defaultGroupBy: "none",
  columns: [
    { id: "state", label: "State", source: "_state", sortable: true, width: 86 },
    { id: "run", label: "Run", source: "_id", sortable: true, width: 132 },
    { id: "started", label: "Started", source: "_started", sortable: true, width: 110 },
    { id: "duration", label: "Duration", source: "_duration", sortable: true, width: 88 },
    {
      id: "score",
      label: "Score",
      source: "score",
      sortable: true,
      align: "right",
      width: 110,
      defaultSort: "desc",
    },
  ],
  rowMapper: (child) => ({
    ...baseRow(child),
    fields: {
      score: {
        kind: "score",
        value: metricNumber(child, "score") ?? child.algorithm_terminal_score ?? null,
        min: 0,
        max: 1,
      },
    },
  }),
};
