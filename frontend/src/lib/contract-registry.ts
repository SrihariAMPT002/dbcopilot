export type ContractEntry = {
  module: string;
  endpoint: string;
  responseType: string;
  hook?: string;
  owner?: string;
};

export const contractRegistry: ContractEntry[] = [
  { module: "governance", endpoint: "/governance/packages/{db_id}", responseType: "GovernancePackage[]", hook: "useGovernance", owner: "intelligence" },
  { module: "semantics", endpoint: "/semantics/{db_id}/package", responseType: "SemanticPackage", hook: "useSemantics", owner: "intelligence" },
  { module: "relationships", endpoint: "/relationships/{db_id}", responseType: "RelationshipPackage", hook: "useRelationships", owner: "intelligence" },
  { module: "kpi", endpoint: "/kpi/{db_id}", responseType: "KpiPackage", hook: "useKPIs", owner: "intelligence" },
  { module: "prompt-studio", endpoint: "/prompt-studio/{db_id}", responseType: "PromptPackageListResponse", hook: "usePromptPackages", owner: "ai-surface" },
  { module: "embeddings", endpoint: "/embeddings/status/{db_id}", responseType: "EmbeddingStatus", hook: "useEmbeddings", owner: "ai-surface" },
  { module: "retrieval", endpoint: "/retrieval/search", responseType: "RetrievalResponse", hook: "useRetrievalSearch", owner: "ai-surface" },
  { module: "agent-memory", endpoint: "/agent-memory/{database_id}", responseType: "AgentMemoryHistoryResponse", hook: "useAgentMemoryHistory", owner: "ai-surface" },
  { module: "business-intelligence", endpoint: "/business-intelligence/health/{db_id}", responseType: "BusinessIntelligenceHealthResponse", hook: "useBusinessIntelligence", owner: "ai-surface" },
  { module: "business-events", endpoint: "/business-events/health/{db_id}", responseType: "BusinessEventsHealthResponse", hook: "useBusinessEventsHealth", owner: "platform" },
];
