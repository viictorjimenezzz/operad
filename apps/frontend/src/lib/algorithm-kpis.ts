import type { RunSummary } from "@/lib/types";

export type KpiSpec = { label: string; value: string; sub?: string };

export function computeAlgorithmKpis(run: RunSummary): KpiSpec[] {
  switch (run.algorithm_class ?? "") {
    case "Sweep":
      return sweepKpis(run);
    case "Beam":
    case "BeamSearch":
      return beamKpis(run);
    case "Debate":
      return debateKpis(run);
    case "EvoGradient":
      return evoKpis(run);
    case "Trainer":
      return trainerKpis(run);
    case "OPRO":
      return oproKpis(run);
    case "SelfRefine":
      return selfRefineKpis(run);
    case "AutoResearcher":
      return autoResearcherKpis(run);
    case "TalkerReasoner":
      return talkerKpis(run);
    case "Verifier":
      return verifierKpis(run);
    default:
      return [];
  }
}

function fmt3(v: number | null | undefined): string {
  return v != null && Number.isFinite(v) ? v.toFixed(3) : "-";
}

function maxOf(nums: (number | null | undefined)[]): number | null {
  const valid = nums.filter((v): v is number => v != null && Number.isFinite(v));
  return valid.length > 0 ? Math.max(...valid) : null;
}

function minOf(nums: (number | null | undefined)[]): number | null {
  const valid = nums.filter((v): v is number => v != null && Number.isFinite(v));
  return valid.length > 0 ? Math.min(...valid) : null;
}

function stdDev(nums: number[]): number | null {
  if (nums.length === 0) return null;
  const mean = nums.reduce((a, b) => a + b, 0) / nums.length;
  const variance = nums.reduce((sum, x) => sum + (x - mean) ** 2, 0) / nums.length;
  return Math.sqrt(variance);
}

function sweepKpis(run: RunSummary): KpiSpec[] {
  const cells = run.generations.length;
  const best = maxOf(run.generations.flatMap((g) => g.scores));
  return [
    { label: "cells", value: String(cells) },
    { label: "best", value: fmt3(best) },
  ];
}

function beamKpis(run: RunSummary): KpiSpec[] {
  const k = run.candidates.length;
  const top = maxOf(run.candidates.map((c) => c.score));
  return [
    { label: "K", value: String(k) },
    { label: "top", value: fmt3(top) },
  ];
}

function debateKpis(run: RunSummary): KpiSpec[] {
  const roundCount = run.rounds.length;
  const lastRound = run.rounds.at(-1);
  const consensus = lastRound ? stdDev(lastRound.scores) : null;
  return [
    { label: "rounds", value: String(roundCount) },
    { label: "consensus", value: fmt3(consensus) },
  ];
}

function evoKpis(run: RunSummary): KpiSpec[] {
  const gens = run.generations.length;
  const pop = run.generations[0]?.scores.length ?? 0;
  const best = maxOf(run.generations.map((g) => g.best));
  return [
    { label: "gens", value: String(gens) },
    { label: "pop", value: String(pop) },
    { label: "best", value: fmt3(best) },
  ];
}

function trainerKpis(run: RunSummary): KpiSpec[] {
  const epochs = maxOf(run.batches.map((b) => b.epoch));
  const bestVal = minOf(
    run.metrics?.val_loss != null ? [run.metrics.val_loss] : [],
  );
  const lr = run.metrics?.lr ?? null;

  const kpis: KpiSpec[] = [
    { label: "epochs", value: epochs != null ? String(Math.round(epochs)) : "-" },
    { label: "best_val", value: fmt3(bestVal) },
  ];
  if (lr != null) kpis.push({ label: "lr", value: lr.toExponential(2) });
  return kpis;
}

function oproKpis(run: RunSummary): KpiSpec[] {
  return [
    { label: "iters", value: String(run.iterations.length) },
    { label: "best", value: fmt3(run.algorithm_terminal_score) },
  ];
}

function selfRefineKpis(run: RunSummary): KpiSpec[] {
  return [
    { label: "iters", value: String(run.iterations.length) },
    { label: "best", value: fmt3(run.algorithm_terminal_score) },
  ];
}

function autoResearcherKpis(run: RunSummary): KpiSpec[] {
  const attempts = run.iterations.filter((it) => it.phase === "plan").length;
  return [
    { label: "attempts", value: String(attempts) },
    { label: "best", value: fmt3(run.algorithm_terminal_score) },
  ];
}

function talkerKpis(run: RunSummary): KpiSpec[] {
  return [{ label: "turns", value: String(run.iterations.length) }];
}

function verifierKpis(run: RunSummary): KpiSpec[] {
  const iters = run.iterations.length;
  const accepted = run.iterations.filter((it) => it.phase === "accepted").length;
  const acc = iters > 0 ? accepted / iters : null;
  return [
    { label: "iters", value: String(iters) },
    { label: "acc", value: acc != null ? `${(acc * 100).toFixed(0)}%` : "-" },
  ];
}
