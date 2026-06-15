import { request } from "./client";
import type { DatabaseSummary, DefaultDatabaseResponse } from "@/types/backend";

export const databasesApi = {
  list: () => request<DatabaseSummary[]>("/databases"),
  default: (databaseId?: number | null) =>
    request<DefaultDatabaseResponse>(`/databases/default${databaseId ? `?database_id=${databaseId}` : ""}`),
  connectionDefaults: () => request<Record<string, number>>("/databases/connection-defaults"),
};
