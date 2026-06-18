export type ObservabilityField = "trace_id" | "request_id" | "model_name" | "usage" | "timestamps" | "latency_ms" | "finish_reason";

export const observabilityRegistry: Record<string, ObservabilityField[]> = {
  governance: ["trace_id", "model_name", "latency_ms", "finish_reason"],
  semantics: ["trace_id", "model_name", "latency_ms", "finish_reason"],
  relationships: ["trace_id", "model_name", "latency_ms", "finish_reason"],
  kpi: ["trace_id", "model_name", "latency_ms", "finish_reason"],
  "prompt-studio": ["trace_id", "request_id", "model_name", "usage", "timestamps", "latency_ms", "finish_reason"],
  embeddings: ["trace_id", "request_id", "model_name", "usage", "timestamps", "latency_ms", "finish_reason"],
  retrieval: ["trace_id", "model_name", "latency_ms", "finish_reason"],
  "agent-memory": ["trace_id", "model_name", "latency_ms", "finish_reason"],
  "business-intelligence": ["trace_id", "model_name", "latency_ms", "finish_reason"],
  "business-events": ["trace_id", "model_name", "latency_ms", "finish_reason"],
};
