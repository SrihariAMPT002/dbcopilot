import { useQuery } from "@tanstack/react-query";
import { EmbeddingService } from "@/services/embeddingsService";

export function useEmbeddings(databaseId?: number | null) {
  return useQuery({
    queryKey: ["embeddings", databaseId ?? "default"],
    queryFn: () => EmbeddingService.getStatus(Number(databaseId)),
    enabled: typeof databaseId === "number" && Number.isFinite(databaseId) && databaseId > 0,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}
