import type { HashKey } from "@/components/ui";
import type { RunInvocation, RunSummary } from "@/lib/types";

export interface CompareParameter {
  fullPath: string;
  type: string;
  value: unknown;
}

export interface CompareRun {
  runId: string;
  summary: RunSummary;
  latestInvocation: RunInvocation | null;
  parameters: CompareParameter[];
  ops: string[];
  hashContent: string;
  langfuseUrl: string | null;
  hashes: Partial<Record<HashKey, string | null>>;
}
