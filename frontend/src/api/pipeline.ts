import { request } from "./client";
import type { PipelineExecutionsResponse, StageExecutionsResponse, StageProgressResponse } from "@/types/backend";

export const pipelineApi = {
  stageProgress: (databaseId: number, parentJobId?: number | null) => {
    const query = parentJobId ? `?parent_job_id=${parentJobId}` : "";
    return request<StageProgressResponse>(`/pipeline/stage-progress/${databaseId}${query}`);
  },
  executions: (databaseId: number, limit = 20) => request<PipelineExecutionsResponse>(`/pipeline/executions/${databaseId}?limit=${limit}`),
  stageExecutions: (databaseId: number, pipelineExecutionId?: number | null, limit = 50) => {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    if (typeof pipelineExecutionId === "number") params.set("pipeline_execution_id", String(pipelineExecutionId));
    return request<StageExecutionsResponse>(`/pipeline/executions/${databaseId}/stages?${params.toString()}`);
  },
};
