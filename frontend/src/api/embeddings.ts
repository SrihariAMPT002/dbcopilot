import { request } from "./client";
import type { EmbeddingStatus } from "@/types/backend";

export const embeddingsApi = {
  status: (databaseId: number) => request<EmbeddingStatus>(`/embeddings/status/${databaseId}`),
  refresh: (databaseId: number) =>
    request(`/embeddings/refresh/${databaseId}`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
};
