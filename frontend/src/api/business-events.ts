import { request } from "./client";
import type { BusinessEventsResponse } from "@/types/backend";

export const businessEventsApi = {
  list: (databaseId: number) => request<BusinessEventsResponse>(`/business-events/${databaseId}`),
};
