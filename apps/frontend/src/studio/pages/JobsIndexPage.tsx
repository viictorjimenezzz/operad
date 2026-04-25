import { useJobs, useStudioManifest } from "@/hooks/use-studio";
import { JobList } from "@/studio/components/job-list";

export function JobsIndexPage() {
  const jobs = useJobs();
  const manifest = useStudioManifest();

  if (jobs.isLoading) {
    return <div className="p-6 text-xs text-muted">loading jobs…</div>;
  }
  return <JobList jobs={jobs.data ?? []} dataDir={manifest.data?.dataDir} />;
}
