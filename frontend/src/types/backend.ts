export type Connection = {
  id: number;
  name: string;
  db_type: string;
  host: string;
  port: number;
  database_name: string;
  username: string;
  ssl_enabled?: boolean;
  status: string;
  lifecycle_status?: string;
  last_sync_at?: string | null;
  created_at?: string;
  disconnected_at?: string | null;
  archived_at?: string | null;
  deleted_at?: string | null;
  deletion_summary?: string | null;
  schema_count?: number;
  table_count?: number;
  last_error?: string | null;
};

export type DashboardSummary = {
  database_id?: number | null;
  database_name?: string | null;
  total_databases: number;
  schemas: number;
  tables: number;
  columns: number;
  relationships: number;
  governance_coverage: number;
  semantic_coverage: number;
  relationship_coverage: number;
  kpi_count: number;
  embeddings_ready: number;
  embeddings_total: number;
  readiness_score: number;
  active_jobs: number;
  last_sync_at?: string | null;
  failed_jobs: number;
  completed_jobs_24h: number;
  failed_jobs_24h: number;
  prompt_packages?: number;
  prompt_embeddings?: number;
  latest_prompt_at?: string | null;
  semantic_cache_entries?: number;
  retrieval_evaluations?: number;
  retrieval_logs?: number;
};

export type DatabaseSummary = {
  database_id: number;
  database_name: string;
  db_type: string;
  status: string;
  lifecycle_status?: string | null;
  connected_at?: string | null;
};

export type DefaultDatabaseResponse = {
  database_id?: number | null;
  database_name?: string | null;
  db_type?: string | null;
  lifecycle_status?: string | null;
  connected_at?: string | null;
};

export type ConnectionRequest = {
  name: string;
  db_type: string;
  host: string;
  port: number;
  database_name: string;
  username: string;
  password: string;
  ssl_enabled: boolean;
};

export type TestConnectionResponse = {
  success: boolean;
  message: string;
  latency_ms?: number | null;
  server_version?: string | null;
  databases_accessible?: number | null;
};

export type SchemaResponse = {
  id: number;
  connected_db_id: number;
  name: string;
  description?: string | null;
  created_at?: string;
  table_count: number;
};

export type TableResponse = {
  id: number;
  schema_id: number;
  name: string;
  table_type: string;
  row_count?: number | null;
  description?: string | null;
  created_at?: string;
  column_count: number;
};

export type ColumnResponse = {
  id: number;
  table_id: number;
  name: string;
  data_type: string;
  ordinal_position?: number | null;
  is_nullable: boolean;
  is_primary_key: boolean;
  is_foreign_key: boolean;
  is_unique: boolean;
  is_indexed: boolean;
  default_value?: string | null;
  max_length?: number | null;
  description?: string | null;
};

export type RelationshipResponse = {
  id: number;
  table_id: number;
  column_name: string;
  referenced_table_name: string;
  referenced_column_name: string;
  referenced_schema?: string | null;
  constraint_name?: string | null;
};

export type SyncLogResponse = {
  id: number;
  connected_db_id: number;
  status: string;
  started_at: string;
  completed_at?: string | null;
  duration_seconds?: number | null;
  schemas_synced: number;
  tables_synced: number;
  columns_synced: number;
  relationships_synced: number;
  error_message?: string | null;
};

export type JobQueueResponse = {
  database_id: number;
  job_id: number;
  job_type: string;
  status: string;
  message: string;
};

export type PipelineRunResponse = {
  database_id: number;
  created_job_ids: number[];
  message: string;
};

export type HealthResponse = {
  status: string;
  version: string;
  db_healthy: boolean;
  timestamp: string;
};

export type GovernanceColumn = {
  column_name: string;
  is_pii: boolean;
  pii_type?: string | null;
  risk_level?: string | null;
  confidence_score?: number;
  business_meaning?: string | null;
  governance_reasoning?: string | null;
};

export type GovernancePackage = {
  id: number;
  database_id: number;
  table_id: number;
  table_name: string;
  schema_name: string;
  table_summary?: string | null;
  business_purpose?: string | null;
  pii_columns: GovernanceColumn[];
  risk_columns: GovernanceColumn[];
  sensitive_columns: GovernanceColumn[];
  overall_risk?: string | null;
  confidence_score?: number;
  evidence?: Array<Record<string, unknown>>;
  rule_matches?: Array<Record<string, unknown>>;
  sample_patterns?: Array<Record<string, unknown> | string>;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  reasoning_tokens?: number | null;
  finish_reason?: string | null;
  latency_ms?: number | null;
  prompt_id?: string | null;
  prompt_version?: string | null;
  model_name?: string | null;
  trace_id?: string | null;
  failure_reason?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type GovernanceSummary = {
  database_id: number;
  table_count: number;
  pii_columns: number;
  risk_columns: number;
  sensitive_columns: number;
  governance_packages: number;
};

export type GovernanceEvidenceItem = {
  id: number;
  governance_package_id: number;
  column_id?: number | null;
  evidence_type: string;
  evidence_source: string;
  evidence_json: Record<string, unknown>;
  created_at?: string | null;
};

export type GovernanceEvidence = {
  database_id: number;
  table_id: number;
  table_name?: string | null;
  schema_name?: string | null;
  confidence_score?: number;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  reasoning_tokens?: number | null;
  finish_reason?: string | null;
  latency_ms?: number | null;
  evidence: GovernanceEvidenceItem[];
};

export type SemanticGlossaryTerm = {
  term: string;
  definition: string;
};

export type SemanticPackage = {
  id?: number;
  database_id: number;
  business_domain?: string | null;
  semantic_summary?: string | null;
  business_entities?: string[];
  business_processes?: string[];
  business_capabilities?: string[];
  business_glossary?: SemanticGlossaryTerm[];
  confidence_score?: number;
  domain_scores?: Record<string, number>;
  evidence?: Array<Record<string, unknown>>;
  prompt_id?: string | null;
  prompt_version?: string | null;
  model_name?: string | null;
  trace_id?: string | null;
};

export type SemanticEvidenceItem = {
  id: number;
  semantic_package_id: number;
  table_id?: number | null;
  evidence_type: string;
  evidence_source: string;
  evidence_json: Record<string, unknown>;
  created_at?: string | null;
};

export type SemanticEvidence = {
  database_id: number;
  business_domain?: string | null;
  confidence_score?: number;
  domain_scores?: Record<string, number>;
  evidence: SemanticEvidenceItem[];
};

export type RelationshipPackageCluster = {
  cluster_id: string;
  parent_cluster_id?: string | null;
  domain_name?: string | null;
  cluster_label?: string | null;
  cluster_summary?: string | null;
  confidence_score?: number;
  cluster_confidence?: number;
  entity_graph?: Array<Record<string, unknown>>;
  hidden_relationships?: Array<Record<string, unknown>>;
  business_process_flows?: Array<Record<string, unknown>>;
  upstream_dependencies?: Array<Record<string, unknown>>;
  downstream_dependencies?: Array<Record<string, unknown>>;
  lifecycle_flows?: Array<Record<string, unknown>>;
  evidence?: Array<Record<string, unknown>>;
  graph_metrics?: Record<string, unknown>;
  confidence_details?: Record<string, unknown>;
  estimated_tokens?: number | null;
  actual_input_tokens?: number | null;
  actual_output_tokens?: number | null;
  prompt_truncated?: boolean | null;
  analysis_status?: string | null;
};

export type RelationshipPackage = {
  database_id: number;
  packages: RelationshipPackageCluster[];
};

export type KpiPackage = {
  id?: number;
  database_id: number;
  kpi_name?: string | null;
  description?: string | null;
  formula?: string | null;
  category?: string | null;
  confidence_score?: number;
  evidence?: Array<Record<string, unknown>>;
  trace_id?: string | null;
  created_at?: string | null;
};

export type BusinessEvent = {
  id?: number;
  event_name: string;
  event_type?: string | null;
  source_tables: string[];
  confidence_score: number;
  trace_id?: string | null;
  created_at?: string | null;
};

export type BusinessEventsResponse = {
  database_id: number;
  events: BusinessEvent[];
};

export type BusinessInsight = {
  id?: number;
  database_id?: number;
  insight_text: string;
  confidence_score: number;
  impact_level?: string | null;
  evidence?: Array<Record<string, unknown>>;
  trace_id?: string | null;
  created_at?: string | null;
};

export type BusinessInsightsResponse = {
  database_id: number;
  insights: BusinessInsight[];
};

export type OpportunityRecommendation = {
  id?: number;
  recommendation_text: string;
  recommendation_type?: string | null;
  confidence_score: number;
  evidence?: Array<Record<string, unknown>>;
  trace_id?: string | null;
  created_at?: string | null;
};

export type OpportunityRecommendationsResponse = {
  database_id: number;
  opportunities: OpportunityRecommendation[];
};

export type DataProduct = {
  id?: number;
  product_name: string;
  product_type?: string | null;
  description?: string | null;
  confidence_score: number;
  evidence?: Array<Record<string, unknown>>;
  trace_id?: string | null;
  created_at?: string | null;
};

export type DataProductsResponse = {
  database_id: number;
  data_products: DataProduct[];
};

export type WarehouseDesign = {
  id?: number;
  design_name: string;
  design_type?: string | null;
  description?: string | null;
  confidence_score: number;
  evidence?: Array<Record<string, unknown>>;
  trace_id?: string | null;
  created_at?: string | null;
};

export type WarehouseDesignsResponse = {
  database_id: number;
  warehouse_designs: WarehouseDesign[];
};

export type Recommendation = {
  id?: number;
  recommendation_text: string;
  recommendation_type?: string | null;
  priority?: string | null;
  confidence_score: number;
  evidence?: Array<Record<string, unknown>>;
  trace_id?: string | null;
  created_at?: string | null;
};

export type RecommendationsResponse = {
  database_id: number;
  recommendations: Recommendation[];
};

export type AgentCapability = {
  id?: number;
  capability_name: string;
  capability_type?: string | null;
  score: number;
  evidence?: Array<Record<string, unknown>>;
  trace_id?: string | null;
  created_at?: string | null;
};

export type AgentMemory = {
  id: number;
  database_id: number;
  query_text: string;
  response_text?: string | null;
  context_json?: Record<string, unknown>;
  memory_type: string;
  tags?: string[];
  embedding_model?: string | null;
  vector_id?: string | null;
  trace_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type AgentMemoryCreateRequest = {
  database_id: number;
  query_text: string;
  response_text?: string | null;
  context_json?: Record<string, unknown>;
  memory_type?: string;
  tags?: string[];
  trace_id?: string | null;
};

export type AgentMemorySearchRequest = {
  database_id: number;
  query: string;
  top_k?: number;
};

export type AgentMemoryHistoryResponse = {
  database_id: number;
  total: number;
  results: AgentMemory[];
};

export type AgentMemorySearchHit = {
  score: number;
  id: number;
  query_text: string;
  response_text?: string | null;
  memory_type: string;
  tags?: string[];
  trace_id?: string | null;
  created_at?: string | null;
};

export type AgentMemorySearchResponse = {
  database_id: number;
  query: string;
  total_hits: number;
  results: AgentMemorySearchHit[];
};

export type PredictiveReadiness = {
  id?: number;
  database_id?: number;
  agent_readiness_score: number;
  text_to_sql_score: number;
  rag_score: number;
  analytics_score: number;
  forecasting_score: number;
  anomaly_detection_score: number;
  ml_score: number;
  agent_capabilities: AgentCapability[];
  evidence?: Array<Record<string, unknown>>;
  trace_id?: string | null;
  created_at?: string | null;
};

export type PredictiveReadinessResponse = {
  database_id: number;
  predictive_readiness: PredictiveReadiness | null;
};

export type ReadinessSnapshot = {
  id?: number;
  database_id: number;
  database_name: string;
  readiness_status: string;
  generated_at: string;
  scores: {
    metadata_score: number;
    semantic_score: number;
    embeddings_score: number;
    relationship_score: number;
    prompt_score: number;
    kpi_score: number;
    overall_score: number;
  };
  category_scores: {
    metadata_readiness_score: number;
    semantic_readiness_score: number;
    relationship_readiness_score: number;
    ai_context_readiness_score: number;
    governance_readiness_score: number;
    kpi_readiness_score: number;
    overall_score: number;
    coverage_percentage: number;
  };
  missing_stages: string[];
  remediation_hints: string[];
  prompt_id?: string | null;
  prompt_version?: string | null;
  model_name?: string | null;
  ai_summary?: string | null;
  ai_recommendations?: string[];
  ai_risks?: string[];
  ai_roadmap?: string[];
  ai_confidence?: number;
};

export type ReadinessHistoryItem = {
  id: number;
  database_id: number;
  overall_score: number;
  maturity_level: string;
  summary?: string | null;
  confidence_score: number;
  trace_id?: string | null;
  model_name?: string | null;
  generated_at: string;
};

export type ReadinessHistoryResponse = {
  database_id: number;
  snapshots: ReadinessHistoryItem[];
};

export type RemediationAction = {
  id: number;
  readiness_snapshot_id: number;
  database_id: number;
  issue: string;
  recommendation: string;
  expected_impact?: string | null;
  priority?: string | null;
  confidence_score: number;
  evidence: string;
  trace_id?: string | null;
  created_at: string;
};

export type ReadinessRemediationResponse = {
  database_id: number;
  latest_snapshot_id?: number | null;
  remediations: RemediationAction[];
};

export type EmbeddingStatus = {
  database_id: number;
  database_name: string;
  embedding_model: string;
  embedding_health: boolean;
  qdrant_health: boolean;
  indexed_tables: number;
  completed_tables: number;
  failed_tables: number;
  vectors_total: number;
  collections: Array<{
    collection_name: string;
    vectors: number;
    indexed_tables?: number;
    last_indexed_at?: string | null;
  }>;
  message?: string;
};

export type SemanticCacheItem = {
  id: number;
  database_id: number;
  query_hash: string;
  query_text: string;
  response: string;
  ttl_seconds: number;
  last_used?: string | null;
  hit_count: number;
  trace_id?: string | null;
  model_name?: string | null;
  created_at: string;
};

export type SemanticCacheListResponse = {
  database_id: number;
  caches: SemanticCacheItem[];
};

export type RetrievalEvaluationItem = {
  id: number;
  database_id: number;
  query_text: string;
  precision_score: number;
  recall_score: number;
  mrr_score: number;
  ndcg_score: number;
  coverage_score: number;
  hallucination_risk: number;
  evidence: string;
  trace_id?: string | null;
  model_name?: string | null;
  created_at: string;
};

export type RetrievalEvaluationListResponse = {
  database_id: number;
  evaluations: RetrievalEvaluationItem[];
};

export type RetrievalMetricsResponse = {
  database_id: number;
  total_documents: number;
  retrieval_logs: number;
  retrieval_evaluations: number;
  collections: Array<{
    collection_name: string;
    vector_count: number;
    status: string;
    embedding_model?: string | null;
    last_synced?: string | null;
  }>;
};

export type RetrievalHit = {
  score: number;
  collection: string;
  database_id: number;
  schema_name: string;
  table_name: string;
  document_type: string;
  content: string;
  metadata: Record<string, unknown>;
  score_breakdown: Record<string, number>;
};

export type RetrievalResponse = {
  query: string;
  database_id?: number | null;
  latency_ms: number;
  total_hits: number;
  results: RetrievalHit[];
};

export type RetrievalRerankedHit = {
  original: RetrievalHit;
  rerank_score: number;
  final_score: number;
  reasoning: string;
};

export type RetrievalRerankResponse = {
  query: string;
  database_id?: number | null;
  latency_ms: number;
  trace_id?: string | null;
  model_name?: string | null;
  results: RetrievalRerankedHit[];
};

export type GraphNode = {
  table_id: number;
  schema_id: number;
  schema_name: string;
  table_name: string;
  table_type: string;
  degree: number;
  in_degree: number;
  out_degree: number;
  depth: number;
  is_isolated: boolean;
};

export type GraphPathStep = {
  source_table_id: number;
  target_table_id: number;
  source_table_name: string;
  target_table_name: string;
  relationship_type: string;
  join_columns: Array<Record<string, unknown>>;
  relationship_strength: number;
};

export type GraphPath = {
  source_table_id: number;
  target_table_id: number;
  hops: number;
  steps: GraphPathStep[];
};

export type GraphRetrievalResponse = {
  database_id?: number | null;
  query: string;
  latency_ms: number;
  neighbors: GraphNode[];
  shortest_paths: GraphPath[];
  contextual_retrieval: GraphNode[];
  lineage: Array<Record<string, unknown>>;
};

export type PromptTemplate = {
  id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  language: string;
  path: string;
};

export type PromptInventoryItem = {
  prompt: string;
  category: string;
  executed: boolean;
  loaded_only: boolean;
  consumer: string;
};

export type PromptBundle = {
  database_id: number;
  bundle_filename: string;
  bundle_mime: string;
  content: string;
  artifacts: Array<{
    artifact_type: string;
    filename?: string;
    mime?: string;
    content: string;
    generated_at?: string;
  }>;
};

export type PromptGenerationRequest = {
  database_id: number;
  artifact_type: string;
  template_id?: string;
};

export type PromptOptimizationRequest = {
  prompt_package_id: number;
};

export type PromptEvaluationRequest = {
  prompt_package_id: number;
};

export type PromptGenerationResponse = {
  generated_prompt: string;
  model: string;
  trace_id?: string | null;
  artifact_id?: number | null;
  prompt_id?: string | null;
  prompt_version?: string | null;
  generated_at?: string | null;
};

export type PromptPackage = {
  id: number;
  database_id: number;
  artifact_type: string;
  template_id?: string | null;
  generated_prompt: string;
  model_name?: string | null;
  trace_id?: string | null;
  prompt_version?: string | null;
  confidence_score: number;
  generation_metadata?: string | null;
  execution_status?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type PromptEmbedding = {
  id: number;
  prompt_package_id: number;
  embedding_model?: string | null;
  vector: string;
  created_at?: string | null;
};

export type PromptPackageListResponse = {
  database_id: number;
  prompt_packages: PromptPackage[];
};

export type PromptVersion = {
  id: number;
  prompt_package_id: number;
  version: number;
  generated_prompt: string;
  model_name?: string | null;
  template_id?: string | null;
  trace_id?: string | null;
  created_at?: string | null;
};

export type PromptVersionListResponse = {
  prompt_package_id: number;
  versions: PromptVersion[];
};

export type PromptObservabilityLog = {
  id: number;
  prompt_package_id: number;
  trace_id?: string | null;
  model_name?: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  reasoning_tokens?: number | null;
  latency_ms?: number | null;
  finish_reason?: string | null;
  execution_status?: string | null;
  failure_reason?: string | null;
  created_at?: string | null;
};

export type PromptObservabilityListResponse = {
  prompt_package_id: number;
  observability_logs: PromptObservabilityLog[];
};

export type PromptEvaluation = {
  id: number;
  prompt_package_id: number;
  completeness_score: number;
  safety_score: number;
  grounding_score: number;
  hallucination_risk: number;
  sql_safety_score: number;
  rag_quality_score: number;
  agent_quality_score: number;
  prompt_quality_score: number;
  reasoning_summary?: string | null;
  packages_used: string;
  evidence: string;
  trace_id?: string | null;
  model_name?: string | null;
  created_at?: string | null;
};

export type PromptBudgetItem = {
  prompt_path: string;
  prompt_id: string;
  category: string;
  version: string;
  current_token_limit: number;
  recommended_token_limit: number;
  truncation_risk: string;
  prompt_quality_score: number;
  description?: string;
};

export type PromptBudgetResponse = {
  total: number;
  prompts: PromptBudgetItem[];
};

export type ConnectionLifecycleResponse = {
  database_id: number;
  database_name: string;
  lifecycle_status: string;
  message: string;
  preserved_resources: Record<string, number>;
  deleted_resources?: Record<string, unknown>;
  trace_id?: string | null;
};

export type ConnectionLifecycleDeleteRequest = {
  delete_metadata?: boolean;
  delete_packages?: boolean;
  delete_embeddings?: boolean;
  delete_observability?: boolean;
};

export type PipelineJob = {
  id: number;
  job_type: string;
  database_id: number;
  status: string;
  progress_percentage: number;
  started_at: string;
  completed_at?: string | null;
  failure_reason?: string | null;
  triggered_by?: string | null;
};

export type PipelineExecution = {
  id: number;
  database_id: number;
  status: string;
  start_time: string;
  end_time?: string | null;
  duration_seconds?: number | null;
  trace_id?: string | null;
  model_name?: string | null;
  token_usage_json?: string | null;
  estimated_input_tokens?: number | null;
  actual_input_tokens?: number | null;
  estimated_output_tokens?: number | null;
  actual_output_tokens?: number | null;
  prompt_size_bytes?: number | null;
  completion_truncated?: boolean | null;
  error_message?: string | null;
  triggered_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type StageExecution = {
  id: number;
  pipeline_execution_id: number;
  database_id: number;
  stage_name: string;
  status: string;
  start_time?: string | null;
  end_time?: string | null;
  duration_seconds?: number | null;
  trace_id?: string | null;
  model_name?: string | null;
  token_usage_json?: string | null;
  estimated_input_tokens?: number | null;
  actual_input_tokens?: number | null;
  estimated_output_tokens?: number | null;
  actual_output_tokens?: number | null;
  prompt_size_bytes?: number | null;
  completion_truncated?: boolean | null;
  error_message?: string | null;
  execution_order?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type PipelineExecutionsResponse = {
  database_id: number;
  executions: PipelineExecution[];
};

export type StageExecutionsResponse = {
  database_id: number;
  pipeline_execution_id?: number | null;
  stage_executions: StageExecution[];
};

export type StageProgressItem = {
  stage: string;
  job_id?: number | null;
  status: string;
  progress_percentage: number;
  retries: number;
  failure_reason?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  depends_on: string[];
};

export type StageProgressResponse = {
  database_id: number;
  parent_job_id?: number | null;
  overall_status: string;
  overall_progress_percentage: number;
  current_stage?: string | null;
  completed_stages: number;
  running_stages: number;
  failed_stages: number;
  pending_stages: number;
  stages: StageProgressItem[];
  graph: Array<{ stage: string; depends_on: string[] }>;
  message: string;
};

export type ObservabilityTraceItem = {
  source_type: string;
  trace_id?: string | null;
  prompt_id?: string | null;
  prompt_version?: string | null;
  model_name?: string | null;
  database_id?: number | null;
  module?: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  reasoning_tokens: number;
  estimated_input_tokens?: number | null;
  actual_input_tokens?: number | null;
  estimated_output_tokens?: number | null;
  actual_output_tokens?: number | null;
  prompt_size_bytes?: number | null;
  completion_truncated?: boolean | null;
  latency_ms: number;
  finish_reason?: string | null;
  execution_status?: string | null;
  estimated_cost_usd: number;
  created_at?: string | null;
  details: Record<string, unknown>;
};

export type ObservabilityTraceListResponse = {
  database_id?: number | null;
  trace_id?: string | null;
  traces: ObservabilityTraceItem[];
};

export type ObservabilityTraceDetailResponse = {
  trace_id: string;
  prompt_id?: string | null;
  prompt_version?: string | null;
  model_name?: string | null;
  latency_ms: number;
  finish_reason?: string | null;
  execution_status?: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  reasoning_tokens: number;
  estimated_input_tokens?: number | null;
  actual_input_tokens?: number | null;
  estimated_output_tokens?: number | null;
  actual_output_tokens?: number | null;
  prompt_size_bytes?: number | null;
  completion_truncated?: boolean | null;
  estimated_cost_usd: number;
  prompt_versions: Array<Record<string, unknown>>;
  pipeline_executions: Array<Record<string, unknown>>;
  stage_executions: Array<Record<string, unknown>>;
  prompt_observability: Array<Record<string, unknown>>;
};
