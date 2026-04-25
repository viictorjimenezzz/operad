import { studioApi } from "@/lib/api/studio";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export function useJobs() {
  return useQuery({ queryKey: ["studio", "jobs"] as const, queryFn: () => studioApi.jobs() });
}

export function useJob(name: string | null | undefined) {
  return useQuery({
    queryKey: ["studio", "job", name] as const,
    queryFn: () => {
      if (!name) throw new Error("useJob: name is required");
      return studioApi.job(name);
    },
    enabled: !!name,
  });
}

export function useRateRow(jobName: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      rowId,
      rating,
      rationale,
    }: { rowId: string; rating: number | null; rationale: string }) =>
      studioApi.rateRow(jobName, rowId, rating, rationale),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["studio", "job", jobName] });
      queryClient.invalidateQueries({ queryKey: ["studio", "jobs"] });
    },
  });
}

export function useStartTraining(jobName: string) {
  return useMutation({
    mutationFn: ({ epochs, lr }: { epochs: number; lr: number }) =>
      studioApi.startTraining(jobName, epochs, lr),
  });
}

export function useStudioManifest() {
  return useQuery({
    queryKey: ["studio", "manifest"] as const,
    queryFn: () => studioApi.manifest(),
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });
}
