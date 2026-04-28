import { HashRow, type HashKey } from "@/components/ui/hash-row";
import { RunInvocationsResponse } from "@/lib/types";

export interface ReproducibilityBlockProps {
  dataInvocations?: unknown;
  invocations?: unknown;
  flat?: boolean;
}

export function ReproducibilityBlock(props: ReproducibilityBlockProps) {
  const raw = props.dataInvocations ?? props.invocations;
  const parsed = RunInvocationsResponse.safeParse(raw);
  if (!parsed.success) return null;

  const rows = parsed.data.invocations;
  const latest = rows[rows.length - 1] ?? null;
  const previous = rows.length >= 2 ? rows[rows.length - 2] : null;

  const current: Partial<Record<HashKey, string | null>> = {
    hash_content: latest?.hash_content ?? null,
    hash_model: latest?.hash_model ?? null,
    hash_prompt: latest?.hash_prompt ?? null,
    hash_input: latest?.hash_input ?? null,
    hash_output_schema: latest?.hash_output_schema ?? null,
    hash_graph: latest?.hash_graph ?? null,
    hash_config: latest?.hash_config ?? null,
  };

  const prev: Partial<Record<HashKey, string | null>> | undefined = previous
    ? {
        hash_content: previous.hash_content ?? null,
        hash_model: previous.hash_model ?? null,
        hash_prompt: previous.hash_prompt ?? null,
        hash_input: previous.hash_input ?? null,
        hash_output_schema: previous.hash_output_schema ?? null,
        hash_graph: previous.hash_graph ?? null,
        hash_config: previous.hash_config ?? null,
      }
    : undefined;

  return <HashRow current={current} {...(prev !== undefined ? { previous: prev } : {})} />;
}
