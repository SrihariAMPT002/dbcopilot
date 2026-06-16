import { useQuery } from "@tanstack/react-query";
import { RetrievalService } from "@/services/retrievalService";

export function useRetrievalSearch(databaseId?: number | null, query = "", topK = 5) {
  return useQuery({
    queryKey: ["retrieval-search", databaseId ?? "default", query, topK],
    queryFn: () => RetrievalService.search({ database_id: databaseId ?? 0, query, top_k: topK }),
    enabled: typeof databaseId === "number" && databaseId > 0 && query.trim().length > 0,
  });
}

export function useRetrievalGraph(databaseId?: number | null, query = "", depth = 2, maxPaths = 5) {
  return useQuery({
    queryKey: ["retrieval-graph", databaseId ?? "default", query, depth, maxPaths],
    queryFn: () => RetrievalService.graph({ database_id: databaseId ?? 0, query, depth, max_paths: maxPaths }),
    enabled: typeof databaseId === "number" && databaseId > 0 && query.trim().length > 0,
  });
}
