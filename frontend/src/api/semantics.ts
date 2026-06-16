import { request } from "./client";
import type { SemanticEvidence, SemanticPackage } from "@/types/backend";

export const semanticsApi = {
  package: (databaseId: number) => request<SemanticPackage>(`/semantics/${databaseId}/package`),
  evidence: (databaseId: number) => request<SemanticEvidence>(`/semantics/evidence/${databaseId}`),
};
