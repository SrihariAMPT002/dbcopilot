import { agentMemoryApi } from "@/api/agent-memory";

export const AgentMemoryService = {
  create: agentMemoryApi.create,
  history: agentMemoryApi.history,
  search: agentMemoryApi.search,
};
