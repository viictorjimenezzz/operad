import { PromptTracebackView } from "@/components/algorithms/trainer/prompt-traceback-view";

export function TrainingTracebackTab({
  runId,
  dataSummary,
}: {
  runId?: string;
  dataSummary?: unknown;
}) {
  return (
    <div className="h-full overflow-auto p-4">
      <PromptTracebackView runId={runId ?? ""} dataSummary={dataSummary} />
    </div>
  );
}
