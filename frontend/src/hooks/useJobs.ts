import { useQuery } from "@tanstack/react-query";
import { ExecutionService } from "@/services/executionService";
import { executionKeys } from "@/lib/execution-keys";

export function useJobs(limit = 20) {
  return useQuery({
    queryKey: executionKeys.jobs(String(limit)),
    queryFn: () => ExecutionService.jobs(limit),
    staleTime: 30_000,
    refetchInterval: 30_000,
    refetchOnWindowFocus: false,
  });
}

export function useStageProgress(databaseId?: number | null, parentJobId?: number | null) {
  return useQuery({
    queryKey: ["execution", "stage-progress", databaseId ?? "default", parentJobId ?? "root"],
    queryFn: () => ExecutionService.stageProgress(Number(databaseId), parentJobId),
    enabled: typeof databaseId === "number" && Number.isFinite(databaseId) && databaseId > 0,
    staleTime: 10_000,
    refetchInterval: (query) => {
      const progress = query.state.data?.overall_status;
      return progress === "running" || progress === "pending" ? 5000 : false;
    },
    refetchOnWindowFocus: false,
  });
}
