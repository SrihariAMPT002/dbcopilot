import { useQuery } from "@tanstack/react-query";
import { ExecutionService } from "@/services/executionService";
import { executionKeys } from "@/lib/execution-keys";

export function usePipelineExecutions(databaseId?: number | null, limit = 20) {
  return useQuery({
    queryKey: executionKeys.pipelineExecutions(databaseId ?? "default", limit),
    queryFn: () => ExecutionService.pipelineExecutions(Number(databaseId ?? 0), limit),
    enabled: typeof databaseId === "number" && databaseId > 0,
    staleTime: 15_000,
    refetchInterval: 30_000,
    refetchOnWindowFocus: false,
  });
}

export function useStageExecutions(databaseId?: number | null, pipelineExecutionId?: number | null, limit = 50) {
  return useQuery({
    queryKey: executionKeys.stageExecutions(databaseId ?? "default", pipelineExecutionId ?? "all", limit),
    queryFn: () => ExecutionService.stageExecutions(Number(databaseId ?? 0), pipelineExecutionId, limit),
    enabled: typeof databaseId === "number" && databaseId > 0,
    staleTime: 15_000,
    refetchInterval: 30_000,
    refetchOnWindowFocus: false,
  });
}
