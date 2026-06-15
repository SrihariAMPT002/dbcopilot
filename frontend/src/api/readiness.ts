import { request } from "./client";
import type { ReadinessSnapshot } from "@/types/backend";

export const readinessApi = {
  snapshot: (databaseId: number) => request<ReadinessSnapshot>(`/readiness/${databaseId}`),
};
