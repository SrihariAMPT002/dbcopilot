import { request } from "./client";
import type { RetrievalResponse, RetrievalRerankResponse, GraphRetrievalResponse } from "@/types/backend";

export type RetrievalRequest = {
  query: string;
  database_id?: number | null;
  top_k?: number;
};

export type GraphRetrievalRequest = {
  query: string;
  database_id?: number | null;
  table_id?: number | null;
  related_table_id?: number | null;
  depth?: number;
  max_paths?: number;
};

export const retrievalApi = {
  search: (payload: RetrievalRequest) =>
    request<RetrievalResponse>("/retrieval/search", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  hybrid: (payload: RetrievalRequest) =>
    request<RetrievalResponse>("/retrieval/hybrid", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  rerank: (payload: RetrievalRequest) =>
    request<RetrievalRerankResponse>("/retrieval/rerank", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  graph: (payload: GraphRetrievalRequest) =>
    request<GraphRetrievalResponse>("/retrieval/graph", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
