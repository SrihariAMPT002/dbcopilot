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
  last_sync_at?: string | null;
  created_at?: string;
  schema_count?: number;
  table_count?: number;
  last_error?: string | null;
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
  prompt_id?: string | null;
  prompt_version?: string | null;
  model_name?: string | null;
  trace_id?: string | null;
  raw_failure_reason?: string | null;
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
  prompt_id?: string | null;
  prompt_version?: string | null;
  model_name?: string | null;
  trace_id?: string | null;
};

export type RelationshipPackageCluster = {
  cluster_id: string;
  parent_cluster_id?: string | null;
  domain_name?: string | null;
  cluster_label?: string | null;
  cluster_summary?: string | null;
  cluster_confidence?: number;
  entity_graph?: Array<Record<string, unknown>>;
  hidden_relationships?: Array<Record<string, unknown>>;
  business_process_flows?: Array<Record<string, unknown>>;
  upstream_dependencies?: Array<Record<string, unknown>>;
  downstream_dependencies?: Array<Record<string, unknown>>;
  lifecycle_flows?: Array<Record<string, unknown>>;
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
  latest: Record<string, unknown>;
  history: Record<string, unknown[]>;
  artifact_count: number;
};

export type ReadinessSnapshot = {
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
