import { useJob } from "@/hooks/use-studio";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { EmptyState } from "@/shared/ui/empty-state";
import { JobRowCard } from "@/studio/components/job-row-card";
import { TrainingLauncher } from "@/studio/components/training-launcher";
import { Link, useParams } from "react-router-dom";

export function JobDetailPage() {
  const { jobName } = useParams<{ jobName: string }>();
  const job = useJob(jobName);

  if (!jobName) return <EmptyState title="missing job name" />;
  if (job.isLoading) return <div className="p-6 text-xs text-muted">loading job…</div>;
  if (job.error || !job.data) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState
          title="job not found"
          description="check the data dir for this job's .jsonl"
          cta={
            <Link to="/">
              <Button variant="primary" size="sm">
                back to jobs
              </Button>
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-4">
      <div className="flex items-center gap-3 text-xs">
        <Link to="/" className="text-muted hover:text-text">
          ← jobs
        </Link>
        <span className="text-muted">/</span>
        <span className="font-mono text-text">{jobName}</span>
        <Badge variant={job.data.rated < job.data.total ? "warn" : "ended"}>
          {job.data.rated} / {job.data.total} rated
        </Badge>
      </div>
      <TrainingLauncher jobName={jobName} />
      <ol className="flex flex-col gap-3">
        {job.data.rows.map((row) => (
          <JobRowCard key={row.id} jobName={jobName} row={row} />
        ))}
      </ol>
    </div>
  );
}
