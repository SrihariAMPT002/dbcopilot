import { request } from "./client";
import type { ReadinessHistoryResponse, ReadinessRemediationResponse, ReadinessSnapshot } from "@/types/backend";

export const readinessApi = {
  snapshot: async (databaseId: number) => {
    try {
      return await request<ReadinessSnapshot>(`/readiness/${databaseId}`);
    } catch (error) {
      if (error instanceof Error && /Request failed: 404/.test(error.message)) {
        return null;
      }
      throw error;
    }
  },
  history: (databaseId: number, filters?: { maturityLevel?: string | null; minScore?: number | null; maxScore?: number | null }) => {
    const params = new URLSearchParams();
    if (filters?.maturityLevel) params.set("maturity_level", filters.maturityLevel);
    if (typeof filters?.minScore === "number") params.set("min_score", String(filters.minScore));
    if (typeof filters?.maxScore === "number") params.set("max_score", String(filters.maxScore));
    const query = params.toString();
    return request<ReadinessHistoryResponse>(`/readiness/history/${databaseId}${query ? `?${query}` : ""}`).catch((error) => {
      if (error instanceof Error && /Request failed: 404/.test(error.message)) {
        return { database_id: databaseId, snapshots: [] } as ReadinessHistoryResponse;
      }
      throw error;
    });
  },
  remediation: async (databaseId: number) => {
    try {
      return await request<ReadinessRemediationResponse>(`/readiness/remediation/${databaseId}`);
    } catch (error) {
      if (error instanceof Error && /Request failed: 404/.test(error.message)) {
        return { database_id: databaseId, remediations: [] } as ReadinessRemediationResponse;
      }
      throw error;
    }
  },
  recalculate: (databaseId: number) =>
    request<ReadinessSnapshot>(`/readiness/recalculate/${databaseId}`, {
      method: "POST",
    }),
};
