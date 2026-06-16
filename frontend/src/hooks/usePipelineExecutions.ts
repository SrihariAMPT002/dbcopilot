import { useQuery } from "@tanstack/react-query";
import { JobService } from "@/services/jobsService";

export function usePipelineExecutions(databaseId?: number | null, limit = 20) {
  return useQuery({
    queryKey: ["pipeline-executions", databaseId ?? "default", limit],
    queryFn: () => JobService.executions(Number(databaseId ?? 0), limit),
    enabled: typeof databaseId === "number" && databaseId > 0,
  });
}

export function useStageExecutions(databaseId?: number | null, pipelineExecutionId?: number | null, limit = 50) {
  return useQuery({
    queryKey: ["stage-executions", databaseId ?? "default", pipelineExecutionId ?? "all", limit],
    queryFn: () => JobService.stageExecutions(Number(databaseId ?? 0), pipelineExecutionId, limit),
    enabled: typeof databaseId === "number" && databaseId > 0,
  });
}
