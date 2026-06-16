import { embeddingsApi } from "@/api/embeddings";

export const EmbeddingService = {
  getStatus: embeddingsApi.status,
  refresh: embeddingsApi.refresh,
};
