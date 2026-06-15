import { useQuery } from "@tanstack/react-query";
import { EmbeddingService } from "@/services/embeddingsService";

export function useEmbeddings(databaseId: number) {
  return useQuery({
    queryKey: ["embeddings", databaseId],
    queryFn: () => EmbeddingService.getStatus(databaseId),
  });
}
