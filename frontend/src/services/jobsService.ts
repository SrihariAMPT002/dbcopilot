import { jobsApi } from "@/api/jobs";
import { pipelineApi } from "@/api/pipeline";

export const JobService = {
  list: jobsApi.list,
  stageProgress: pipelineApi.stageProgress,
  executions: pipelineApi.executions,
  stageExecutions: pipelineApi.stageExecutions,
};
