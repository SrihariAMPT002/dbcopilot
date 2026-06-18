import { request } from "./client";
import type { BusinessEventsHealthResponse, BusinessEventsResponse } from "@/types/backend";

export const businessEventsApi = {
  list: (databaseId: number) => request<BusinessEventsResponse>(`/business-events/${databaseId}`),
  health: (databaseId: number) => request<BusinessEventsHealthResponse>(`/business-events/health/${databaseId}`),
};
