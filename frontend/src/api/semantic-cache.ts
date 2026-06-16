import { request } from "./client";
import type { SemanticCacheListResponse } from "@/types/backend";

export const semanticCacheApi = {
  list: (databaseId: number) => request<SemanticCacheListResponse>(`/semantic-cache/${databaseId}`),
};
