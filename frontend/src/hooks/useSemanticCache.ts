import { useQuery } from "@tanstack/react-query";
import { SemanticCacheService } from "@/services/semanticCacheService";

export function useSemanticCache(databaseId?: number | null) {
  return useQuery({
    queryKey: ["semantic-cache", databaseId ?? "default"],
    queryFn: () => SemanticCacheService.list(databaseId ?? 0),
    enabled: typeof databaseId === "number" && databaseId > 0,
  });
}
