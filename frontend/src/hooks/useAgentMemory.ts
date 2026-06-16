import { useQuery } from "@tanstack/react-query";
import { AgentMemoryService } from "@/services/agentMemoryService";

export function useAgentMemoryHistory(databaseId?: number | null, limit = 20) {
  return useQuery({
    queryKey: ["agent-memory-history", databaseId ?? "default", limit],
    queryFn: () => AgentMemoryService.history(databaseId ?? 0, limit),
    enabled: typeof databaseId === "number" && databaseId > 0,
  });
}

export function useAgentMemorySearch(databaseId?: number | null, query = "", topK = 5) {
  return useQuery({
    queryKey: ["agent-memory-search", databaseId ?? "default", query, topK],
    queryFn: () => AgentMemoryService.search({ database_id: databaseId ?? 0, query, top_k: topK }),
    enabled: typeof databaseId === "number" && databaseId > 0 && query.trim().length > 0,
  });
}
