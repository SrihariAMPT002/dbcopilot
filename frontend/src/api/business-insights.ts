import { request } from "./client";
import type { BusinessInsightsResponse } from "@/types/backend";

export const businessInsightsApi = {
  list: (databaseId: number) => request<BusinessInsightsResponse>(`/business-insights/${databaseId}`),
};
