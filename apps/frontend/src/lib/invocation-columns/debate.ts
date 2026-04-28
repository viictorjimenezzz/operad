import type { AlgorithmColumns } from "@/lib/invocation-columns/types";
import {
  baseRow,
  metadataNumber,
  metadataString,
  metricNumber,
} from "@/lib/invocation-columns/types";

export const debateColumns: AlgorithmColumns = {
  algorithmClass: "Debate",
  defaultGroupBy: "round",
  columns: [
    { id: "state", label: "State", source: "_state", sortable: true, width: 86 },
    { id: "round", label: "Round", source: "round", sortable: true, align: "right", width: 78 },
    { id: "speaker", label: "Speaker", source: "speaker", sortable: true, width: 120 },
    { id: "claim", label: "Claim", source: "claim", width: "1fr" },
    {
      id: "score",
      label: "Score",
      source: "score",
      sortable: true,
      align: "right",
      width: 112,
      defaultSort: "desc",
    },
    { id: "latency", label: "Latency", source: "_duration", sortable: true, align: "right", width: 88 },
  ],
  rowMapper: (child, _parent, _index, previous) => ({
    ...baseRow(child),
    fields: {
      round: {
        kind: "num",
        value: metadataNumber(child, "round", "round_index"),
        format: "int",
      },
      speaker: { kind: "text", value: metadataString(child, "speaker", "side") ?? "unknown", mono: true },
      claim: {
        kind: "diff",
        value: metadataString(child, "claim", "text") ?? "—",
        previous: previous ? (metadataString(previous, "claim", "text") ?? undefined) : undefined,
      },
      score: { kind: "score", value: metricNumber(child, "score"), min: 0, max: 1 },
    },
  }),
};
