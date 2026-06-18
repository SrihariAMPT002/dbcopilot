export const executionKeys = {
  jobs: (statusFilter: string) => ["execution", "jobs", statusFilter],
  pipelineExecutions: (databaseId: number | string, limit: number) => ["execution", "pipeline-executions", databaseId, limit],
  stageExecutions: (databaseId: number | string, pipelineExecutionId: number | string, limit: number) => [
    "execution",
    "stage-executions",
    databaseId,
    pipelineExecutionId,
    limit,
  ],
  observabilityTraceDetail: (databaseId: number | string, traceId: string) => ["execution", "trace-detail", databaseId, traceId],
};
