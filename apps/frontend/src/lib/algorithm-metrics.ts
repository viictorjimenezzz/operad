import type { RunSummary } from "@/lib/types";

type MetricFn = (run: RunSummary) => string;

const registry: Record<string, MetricFn> = {
  EvoGradient: (r) => {
    const last = r.generations.at(-1);
    return last?.best != null ? `best=${last.best.toFixed(3)}` : "—";
  },
  Trainer: (r) => {
    const last = r.batches.at(-1);
    return last?.epoch != null ? `epoch=${last.epoch}` : "—";
  },
  Debate: (r) => `rounds=${r.rounds.length}`,
  BeamSearch: (r) => {
    const best = r.candidates.reduce<number | null>(
      (acc, c) => (c.score != null && (acc == null || c.score > acc) ? c.score : acc),
      null,
    );
    return best != null ? `top=${best.toFixed(3)}` : "—";
  },
};

const fallback: MetricFn = (r) =>
  r.algorithm_terminal_score != null
    ? `score=${r.algorithm_terminal_score.toFixed(3)}`
    : `events=${r.event_total}`;

export function getAlgorithmMetric(run: RunSummary): string {
  const fn = run.algorithm_class ? registry[run.algorithm_class] : undefined;
  return (fn ?? fallback)(run);
}
