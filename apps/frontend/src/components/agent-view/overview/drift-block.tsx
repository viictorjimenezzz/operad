import { Section } from "@/components/ui";
import { dashboardApi } from "@/lib/api/dashboard";
import { RunInvocationsResponse } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";

export interface DriftBlockProps {
  dataInvocations?: unknown;
  invocations?: unknown;
  runId?: string;
  defaultOpen?: boolean;
}

export function DriftBlock(props: DriftBlockProps) {
  const parsed = RunInvocationsResponse.safeParse(props.dataInvocations ?? props.invocations);
  const invocations = parsed.success ? parsed.data.invocations : [];

  const driftQuery = useQuery({
    queryKey: ["run", "drift", props.runId] as const,
    queryFn: () => dashboardApi.drift(props.runId ?? ""),
    enabled: !!props.runId,
    retry: false,
    staleTime: 30_000,
  });

  const drift = driftQuery.data ?? [];
  const promptHashes = new Set(invocations.map((r) => r.hash_prompt).filter(Boolean));
  const driftCount = drift.length;
  const summary =
    invocations.length < 2
      ? "needs 2+ invocations"
      : driftCount > 0
        ? `${driftCount} prompt change${driftCount === 1 ? "" : "s"} recorded`
        : promptHashes.size > 1
          ? `${promptHashes.size} unique prompts across ${invocations.length} invocations`
          : "no drift — single prompt across all invocations";

  const disabled = invocations.length < 2;

  return (
    <Section
      title="Prompt drift"
      summary={summary}
      disabled={disabled}
      defaultOpen={props.defaultOpen ?? false}
    >
      {drift.length === 0 ? (
        <div className="text-[12px] text-muted">
          {promptHashes.size > 1
            ? "Prompt hashes differ across invocations — but no drift events were recorded by the optimizer (this often means the change came from outside the training loop)."
            : "Same prompt was used for every invocation in this run."}
        </div>
      ) : (
        <ol className="space-y-2">
          {drift.map((row, i) => (
            <li key={i} className="rounded-lg bg-bg-inset p-3">
              <div className="mb-1 flex items-center gap-2 text-[11px] uppercase tracking-[0.06em] text-muted">
                <span>epoch {row.epoch}</span>
                {row.selected_path ? (
                  <span className="font-mono text-text">· {row.selected_path}</span>
                ) : null}
                {row.changed_params.length > 0 ? (
                  <span>· {row.changed_params.length} params</span>
                ) : null}
              </div>
              {row.critique ? (
                <div className="mb-2 text-[12px] text-text">{row.critique}</div>
              ) : null}
              {row.changes.map((c, j) => (
                <div key={j} className="space-y-1">
                  {c.path ? (
                    <div className="font-mono text-[10px] text-muted-2">{c.path}</div>
                  ) : null}
                  <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                    <div className="rounded bg-[--color-err-dim]/40 p-2 text-[--color-err]">
                      − {c.before_text}
                    </div>
                    <div className="rounded bg-[--color-ok-dim]/40 p-2 text-[--color-ok]">
                      + {c.after_text}
                    </div>
                  </div>
                </div>
              ))}
            </li>
          ))}
        </ol>
      )}
    </Section>
  );
}
