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
  history: (databaseId: number, limit = 20) =>
    request<AgentMemoryHistoryResponse>(`/agent-memory/${databaseId}?limit=${limit}`),
  search: (payload: AgentMemorySearchRequest) =>
    request<AgentMemorySearchResponse>("/agent-memory/search", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
