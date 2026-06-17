import { request } from "./client";
import type { EmbeddingStatus } from "@/types/backend";

export const embeddingsApi = {
  status: async (databaseId: number) => {
    try {
      return await request<EmbeddingStatus>(`/embeddings/status/${databaseId}`);
    } catch (error) {
      if (error instanceof Error && /Request failed: 404/.test(error.message)) {
        return {
          database_id: databaseId,
          database_name: "n/a",
          embedding_model: "n/a",
          embedding_health: false,
          qdrant_health: false,
          indexed_tables: 0,
          completed_tables: 0,
          failed_tables: 0,
          vectors_total: 0,
          collections: [],
        } as EmbeddingStatus;
      }
      throw error;
    }
  },
  refresh: (databaseId: number) =>
    request(`/embeddings/refresh/${databaseId}`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
};
