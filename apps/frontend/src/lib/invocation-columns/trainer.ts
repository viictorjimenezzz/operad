import type { AlgorithmColumns } from "@/lib/invocation-columns/types";
import {
  baseRow,
  metadataNumber,
  metadataString,
  metricNumber,
} from "@/lib/invocation-columns/types";

function phaseTone(
  phase: string,
): "ok" | "warn" | "error" | "live" | "accent" | "default" {
  if (phase === "train" || phase === "step") return "live";
  if (phase === "eval" || phase === "validation") return "accent";
  if (phase === "error") return "error";
  return "default";
}

export const trainerColumns: AlgorithmColumns = {
  algorithmClass: "Trainer",
  defaultGroupBy: "epoch",
  columns: [
    { id: "state", label: "State", source: "_state", sortable: true, width: 86 },
    { id: "epoch", label: "Epoch", source: "epoch", sortable: true, align: "right", width: 72 },
    { id: "batch", label: "Batch", source: "batch", sortable: true, align: "right", width: 72 },
    { id: "phase", label: "Phase", source: "phase", sortable: true, width: 104 },
    {
      id: "trainLoss",
      label: "Train loss",
      source: "trainLoss",
      sortable: true,
      align: "right",
      width: 120,
      defaultSort: "asc",
    },
    { id: "valLoss", label: "Val loss", source: "valLoss", sortable: true, align: "right", width: 112 },
    { id: "lr", label: "LR", source: "lr", sortable: true, align: "right", width: 96 },
  ],
  rowMapper: (child) => {
    const phase = metadataString(child, "phase") ?? "step";
    return {
      ...baseRow(child),
      fields: {
        epoch: { kind: "num", value: metadataNumber(child, "epoch"), format: "int" },
        batch: { kind: "num", value: metadataNumber(child, "batch", "batch_index"), format: "int" },
        phase: { kind: "pill", value: phase, tone: phaseTone(phase) },
        trainLoss: { kind: "score", value: metricNumber(child, "train_loss", "loss"), min: 0 },
        valLoss: { kind: "score", value: metricNumber(child, "val_loss"), min: 0 },
        lr: { kind: "param", value: metricNumber(child, "lr"), format: "number" },
      },
    };
  },
};
