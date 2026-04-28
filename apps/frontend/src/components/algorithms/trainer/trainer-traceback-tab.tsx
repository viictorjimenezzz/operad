import { PromptTracebackView } from "@/components/algorithms/trainer/prompt-traceback-view";
import { EmptyState } from "@/components/ui";

interface TrainerTracebackTabProps {
  runId?: string;
  dataSummary?: unknown;
}

export function TrainerTracebackTab({ runId, dataSummary }: TrainerTracebackTabProps) {
  const tracebackPath = summaryTracebackPath(dataSummary);

  return (
    <div className="h-full overflow-auto p-4">
      {tracebackPath ? (
        <PromptTracebackView runId={runId ?? ""} dataSummary={dataSummary} />
      ) : (
        <EmptyState
          title="no traceback recorded"
          description="this run did not save a PromptTraceback; see PromptTraceback.save() in your training script"
        />
      )}
    </div>
  );
}

function summaryTracebackPath(dataSummary: unknown): string | null {
  if (!dataSummary || typeof dataSummary !== "object" || Array.isArray(dataSummary)) {
    return null;
  }
  const summary = dataSummary as Record<string, unknown>;
  const bySnake = summary.traceback_path;
  if (typeof bySnake === "string" && bySnake.length > 0) return bySnake;
  const byCamel = summary.tracebackPath;
  if (typeof byCamel === "string" && byCamel.length > 0) return byCamel;
  return null;
}
