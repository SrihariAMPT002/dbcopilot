import { jobsApi } from "@/api/jobs";
import { pipelineApi } from "@/api/pipeline";
import { observabilityApi } from "@/api/observability";

export const ExecutionService = {
  jobs: jobsApi.list,
  pipelineExecutions: pipelineApi.executions,
  stageExecutions: pipelineApi.stageExecutions,
  stageProgress: pipelineApi.stageProgress,
  traceDetail: observabilityApi.traceDetail,
};
