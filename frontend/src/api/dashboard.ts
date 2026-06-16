import { request } from "./client";
import type { DashboardSummary } from "@/types/backend";

export const dashboardApi = {
  summary: (databaseId?: number | null) => {
    const query = databaseId ? `?database_id=${databaseId}` : "";
    return request<DashboardSummary>(`/dashboard${query}`);
  },
};
