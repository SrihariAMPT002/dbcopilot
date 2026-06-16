import { retrievalApi, type GraphRetrievalRequest, type RetrievalRequest } from "@/api/retrieval";

export const RetrievalService = {
  search: (payload: RetrievalRequest) => retrievalApi.search(payload),
  hybrid: (payload: RetrievalRequest) => retrievalApi.hybrid(payload),
  rerank: (payload: RetrievalRequest) => retrievalApi.rerank(payload),
  graph: (payload: GraphRetrievalRequest) => retrievalApi.graph(payload),
};
