import { request } from "./client";
import type { RetrievalMetricsResponse, RetrievalRegistryResponse } from "@/types/backend";

export const retrievalMetricsApi = {
  get: (databaseId: number) => request<RetrievalMetricsResponse>(`/retrieval/metrics/${databaseId}`),
  registry: () => request<RetrievalRegistryResponse>("/retrieval/registry"),
};
