import { retrievalMetricsApi } from "@/api/retrieval-metrics";

export const RetrievalMetricsService = {
  get: retrievalMetricsApi.get,
  registry: retrievalMetricsApi.registry,
};
