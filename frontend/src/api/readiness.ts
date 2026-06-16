import { request } from "./client";
import type { ReadinessHistoryResponse, ReadinessRemediationResponse, ReadinessSnapshot } from "@/types/backend";

export const readinessApi = {
  snapshot: (databaseId: number) => request<ReadinessSnapshot>(`/readiness/${databaseId}`),
  history: (databaseId: number, filters?: { maturityLevel?: string | null; minScore?: number | null; maxScore?: number | null }) => {
    const params = new URLSearchParams();
    if (filters?.maturityLevel) params.set("maturity_level", filters.maturityLevel);
    if (typeof filters?.minScore === "number") params.set("min_score", String(filters.minScore));
    if (typeof filters?.maxScore === "number") params.set("max_score", String(filters.maxScore));
    const query = params.toString();
    return request<ReadinessHistoryResponse>(`/readiness/history/${databaseId}${query ? `?${query}` : ""}`);
  },
  remediation: (databaseId: number) => request<ReadinessRemediationResponse>(`/readiness/remediation/${databaseId}`),
  recalculate: (databaseId: number) =>
    request<ReadinessSnapshot>(`/readiness/recalculate/${databaseId}`, {
      method: "POST",
    }),
};
