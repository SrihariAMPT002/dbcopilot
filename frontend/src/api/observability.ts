import { request } from "./client";

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
  context_source?: string | null;
  used_context?: boolean | null;
  fallback_reason?: string | null;
  deployment?: string | null;
  module?: string | null;
  artifact_type?: string | null;
  database_id?: number | null;
  latency_ms: number;
  finish_reason?: string | null;
  execution_status?: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  reasoning_tokens: number;
  estimated_cost_usd: number;
  prompt_versions: Array<Record<string, unknown>>;
  pipeline_executions: Array<Record<string, unknown>>;
  stage_executions: Array<Record<string, unknown>>;
  prompt_observability: Array<Record<string, unknown>>;
};

export type LifecycleEvent = {
  id: number;
  connected_db_id: number;
  event_type: string;
  actor?: string | null;
  reason?: string | null;
  trace_id?: string | null;
  metadata_json?: string | null;
  created_at?: string | null;
};

export type LifecycleEventsResponse = {
  database_id: number;
  events: LifecycleEvent[];
};

export const observabilityApi = {
  traces: (
    databaseId: number,
    filters?: { module?: string; model_name?: string; trace_id?: string; from_date?: string; to_date?: string },
  ) => {
    const params = new URLSearchParams();
    if (filters?.module) params.set("module", filters.module);
    if (filters?.model_name) params.set("model_name", filters.model_name);
    if (filters?.trace_id) params.set("trace_id", filters.trace_id);
    if (filters?.from_date) params.set("from_date", filters.from_date);
    if (filters?.to_date) params.set("to_date", filters.to_date);
    const query = params.toString();
    return request<ObservabilityTraceListResponse>(`/observability/${databaseId}${query ? `?${query}` : ""}`);
  },
  traceDetail: (databaseId: number, traceId: string) => request<ObservabilityTraceDetailResponse>(`/observability/${databaseId}/${encodeURIComponent(traceId)}`),
  lifecycleEvents: (databaseId: number) => request<LifecycleEventsResponse>(`/observability/${databaseId}/events`),
};
