import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import type { JobSummary } from "@/lib/types";
import { Link } from "react-router-dom";

interface JobListProps {
  jobs: JobSummary[];
  dataDir?: string | undefined;
}

export function JobList({ jobs, dataDir }: JobListProps) {
  if (jobs.length === 0) {
    return (
      <EmptyState
        title="no jobs found"
        description={
          <>
            drop <code className="rounded bg-bg-2 px-1 py-0.5 font-mono">*.jsonl</code> files into{" "}
            <code className="rounded bg-bg-2 px-1 py-0.5 font-mono">{dataDir ?? "<data dir>"}</code>
          </>
        }
      />
    );
  }
  return (
    <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
      {jobs.map((job) => (
        <Card key={job.name}>
          <CardHeader>
            <CardTitle className="font-mono normal-case tracking-normal text-text">
              {job.name}
            </CardTitle>
            <Badge variant={job.unrated > 0 ? "warn" : "ended"}>
              {job.rated_rows}/{job.total_rows}
            </Badge>
          </CardHeader>
          <CardContent>
            <p className="m-0 text-xs text-muted">
              {job.unrated > 0
                ? `${job.unrated} row${job.unrated === 1 ? "" : "s"} still need rating`
                : "all rows rated"}
            </p>
            <div className="mt-3 flex items-center gap-2">
              <Link to={`/jobs/${encodeURIComponent(job.name)}`}>
                <Button variant="primary" size="sm">
                  open
                </Button>
              </Link>
              <a
                href={`/jobs/${encodeURIComponent(job.name)}/download`}
                className="text-[11px] text-muted hover:text-text"
              >
                download
              </a>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
