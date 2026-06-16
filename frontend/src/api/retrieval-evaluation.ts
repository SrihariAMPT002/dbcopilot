import { request } from "./client";
import type { RetrievalEvaluationListResponse } from "@/types/backend";

export const retrievalEvaluationApi = {
  list: (databaseId: number) => request<RetrievalEvaluationListResponse>(`/retrieval/evaluation/${databaseId}`),
};
