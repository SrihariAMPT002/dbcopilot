import { useQuery } from "@tanstack/react-query";
import { AgentMemoryService } from "@/services/agentMemoryService";
import { queryKeys } from "@/lib/query-keys";

export function useAgentMemoryHistory(databaseId?: number | null, limit = 20) {
  return useQuery({
    queryKey: queryKeys.agentMemoryHistory(databaseId ?? "default", limit),
    queryFn: () => AgentMemoryService.history(databaseId ?? 0, limit),
    enabled: typeof databaseId === "number" && databaseId > 0,
  });
}

export function useAgentMemorySearch(databaseId?: number | null, query = "", topK = 5) {
  return useQuery({
    queryKey: queryKeys.agentMemorySearch(databaseId ?? "default", query, topK),
    queryFn: () => AgentMemoryService.search({ database_id: databaseId ?? 0, query, top_k: topK }),
    enabled: typeof databaseId === "number" && databaseId > 0 && query.trim().length > 0,
  });
}

export function useAgentMemoryHealth(databaseId?: number | null) {
  return useQuery({
    queryKey: queryKeys.agentMemoryHealth(databaseId ?? "default"),
    queryFn: () => AgentMemoryService.health(databaseId ?? 0),
    enabled: typeof databaseId === "number" && databaseId > 0,
    staleTime: 60_000,
  });
}
