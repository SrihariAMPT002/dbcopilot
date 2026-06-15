import { request } from "./client";
import type { ColumnResponse, RelationshipResponse, SchemaResponse, TableResponse, SyncLogResponse } from "@/types/backend";

export const metadataApi = {
  schemas: (dbId: number) => request<SchemaResponse[]>(`/metadata/databases/${dbId}/schemas`),
  tables: (schemaId: number) => request<TableResponse[]>(`/metadata/schemas/${schemaId}/tables`),
  columns: (tableId: number) => request<ColumnResponse[]>(`/metadata/tables/${tableId}/columns`),
  relationships: (tableId: number) => request<RelationshipResponse[]>(`/metadata/tables/${tableId}/relationships`),
  syncLogs: (dbId: number, limit = 10) => request<SyncLogResponse[]>(`/metadata/databases/${dbId}/sync-logs?limit=${limit}`),
  diagnose: (dbId: number) => request<Record<string, unknown>>(`/metadata/diagnose/${dbId}`),
};
