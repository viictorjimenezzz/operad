import type { AlgorithmColumns } from "@/lib/invocation-columns/types";
import {
  asRecord,
  baseRow,
  langfuseField,
  metadataNumber,
  metadataString,
  metadataValue,
  metricNumber,
} from "@/lib/invocation-columns/types";

export const sweepColumns: AlgorithmColumns = {
  algorithmClass: "Sweep",
  defaultGroupBy: "cell",
  columns: [
    { id: "state", label: "State", source: "_state", sortable: true, width: 86 },
    { id: "cell", label: "Cell", source: "cell", sortable: true, width: 76 },
    { id: "axes", label: "Axes", source: "axes", width: "1fr" },
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
    { id: "langfuse", label: "Langfuse", source: "langfuse", width: 86 },
  ],
  rowMapper: (child) => {
    const axisValues = asRecord(
      metadataValue(child, "axis_values") ?? metadataValue(child, "algorithm_axis_values"),
    );
    return {
      ...baseRow(child),
      fields: {
        cell: {
          kind: "num",
          value: metadataNumber(child, "cell", "cell_index"),
          format: "int",
        },
        axes: { kind: "param", value: axisValues ?? metadataString(child, "axis_values") ?? "—" },
        score: { kind: "score", value: metricNumber(child, "score"), min: 0, max: 1 },
        cost: { kind: "num", value: child.cost?.cost_usd ?? null, format: "cost" },
        langfuse: langfuseField(child),
      },
    };
  },
};
