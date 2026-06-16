import { request } from "./client";
import type { RetrievalMetricsResponse } from "@/types/backend";

export const retrievalMetricsApi = {
  get: (databaseId: number) => request<RetrievalMetricsResponse>(`/retrieval/metrics/${databaseId}`),
};
