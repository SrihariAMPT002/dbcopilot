import { request } from "./client";
import type { EmbeddingStatus } from "@/types/backend";

export const embeddingsApi = {
  status: (databaseId: number) => request<EmbeddingStatus>(`/embeddings/status/${databaseId}`),
};
