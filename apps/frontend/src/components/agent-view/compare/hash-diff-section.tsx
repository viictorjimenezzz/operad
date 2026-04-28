import { CompareSection } from "@/components/agent-view/compare/compare-section";
import type { CompareRun } from "@/components/agent-view/compare/types";
import { hashColor } from "@/lib/hash-color";
import { truncateMiddle } from "@/lib/utils";

const KEYS = [
  "hash_model",
  "hash_prompt",
  "hash_input",
  "hash_output_schema",
  "hash_config",
  "hash_graph",
  "hash_content",
] as const;

export function HashDiffSection({ runs }: { runs: CompareRun[] }) {
  const reference = runs[0] ?? null;
  return (
    <CompareSection title="Hash Diff Matrix">
      <div
        className="grid"
        style={{ gridTemplateColumns: `160px repeat(${runs.length}, minmax(0, 1fr))` }}
      >
        <div className="border-b border-border px-2 py-1 text-[10px] uppercase tracking-[0.06em] text-muted">
          hash key
        </div>
        {runs.map((run) => (
          <div key={run.runId} className="border-b border-l border-border">
            <div className="h-1 w-full" style={{ background: hashColor(run.hashContent) }} />
            <div className="px-2 py-1 font-mono text-[10px] text-text">{truncateMiddle(run.runId, 14)}</div>
          </div>
        ))}
        {KEYS.map((key) => (
          <HashMatrixRow key={key} hashKey={key} runs={runs} reference={reference} />
        ))}
      </div>
    </CompareSection>
  );
}

function HashMatrixRow({
  hashKey,
  runs,
  reference,
}: {
  hashKey: (typeof KEYS)[number];
  runs: CompareRun[];
  reference: CompareRun | null;
}) {
  const baseline = reference?.hashes[hashKey] ?? null;
  return (
    <>
      <div className="border-b border-border px-2 py-1 font-mono text-[11px] text-muted">{hashKey}</div>
      {runs.map((run, index) => {
        const value = run.hashes[hashKey] ?? null;
        const changed = index > 0 && value !== baseline;
        return (
          <div
            key={`${run.runId}:${hashKey}`}
            data-hash-diff={changed ? "changed" : "same"}
            className={[
              "border-b border-l border-border px-2 py-1 font-mono text-[11px]",
              changed ? "bg-[--color-warn]/15 text-text" : "text-muted",
            ].join(" ")}
          >
            {value ? truncateMiddle(value, 12) : "—"}
          </div>
        );
      })}
    </>
  );
}
