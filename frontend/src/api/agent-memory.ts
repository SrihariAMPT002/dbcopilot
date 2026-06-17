import { request } from "./client";
import type {
  AgentMemoryCreateRequest,
  AgentMemory,
  AgentMemoryHistoryResponse,
  AgentMemorySearchRequest,
  AgentMemorySearchResponse,
} from "@/types/backend";

export const agentMemoryApi = {
  create: (payload: AgentMemoryCreateRequest) =>
    request<AgentMemory>("/agent-memory", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  history: async (databaseId: number, limit = 20) => {
    try {
      return await request<AgentMemoryHistoryResponse>(`/agent-memory/${databaseId}?limit=${limit}`);
    } catch (error) {
      if (error instanceof Error && /Request failed: 404/.test(error.message)) {
        return { database_id: databaseId, total: 0, results: [] } as AgentMemoryHistoryResponse;
      }
      throw error;
    }
  },
  search: (payload: AgentMemorySearchRequest) =>
    request<AgentMemorySearchResponse>("/agent-memory/search", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
