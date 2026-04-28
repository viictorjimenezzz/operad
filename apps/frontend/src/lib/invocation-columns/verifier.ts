import type { AlgorithmColumns } from "@/lib/invocation-columns/types";
import {
  baseRow,
  diffField,
  metadataBoolean,
  metadataNumber,
  metadataString,
  metricNumber,
} from "@/lib/invocation-columns/types";

function acceptedTone(
  accepted: boolean,
): "ok" | "warn" | "error" | "live" | "accent" | "default" {
  return accepted ? "ok" : "error";
}

export const verifierColumns: AlgorithmColumns = {
  algorithmClass: "Verifier",
  defaultGroupBy: "iter",
  columns: [
    { id: "state", label: "State", source: "_state", sortable: true, width: 86 },
    { id: "iter", label: "Iter", source: "iter", sortable: true, align: "right", width: 68 },
    { id: "candidate", label: "Candidate", source: "candidate", width: "1fr" },
    {
      id: "score",
      label: "Score",
      source: "score",
      sortable: true,
      align: "right",
      width: 110,
      defaultSort: "desc",
    },
    { id: "accepted", label: "Accepted", source: "accepted", sortable: true, width: 96 },
    { id: "cost", label: "Cost", source: "cost", sortable: true, align: "right", width: 84 },
  ],
  rowMapper: (child, _parent, _index, previous) => {
    const accepted = metadataBoolean(child, "accepted", "is_accepted") ?? false;
    return {
      ...baseRow(child),
      fields: {
        iter: { kind: "num", value: metadataNumber(child, "iter", "iter_index"), format: "int" },
        candidate: diffField(
          metadataString(child, "candidate_text", "text") ?? "—",
          previous ? (metadataString(previous, "candidate_text", "text") ?? undefined) : undefined,
        ),
        score: { kind: "score", value: metricNumber(child, "score") ?? child.algorithm_terminal_score ?? null },
        accepted: {
          kind: "pill",
          value: accepted ? "accepted" : "rejected",
          tone: acceptedTone(accepted),
        },
        cost: { kind: "num", value: child.cost?.cost_usd ?? null, format: "cost" },
      },
    };
  },
};
