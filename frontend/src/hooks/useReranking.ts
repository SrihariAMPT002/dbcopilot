import { useQuery } from "@tanstack/react-query";
import { RetrievalService } from "@/services/retrievalService";

export function useReranking(databaseId?: number | null, query = "", topK = 5) {
  return useQuery({
    queryKey: ["reranking", databaseId ?? "default", query, topK],
    queryFn: () => RetrievalService.rerank({ database_id: databaseId ?? 0, query, top_k: topK }),
    enabled: typeof databaseId === "number" && databaseId > 0 && query.trim().length > 0,
  });
}
