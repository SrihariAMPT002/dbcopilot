import { request } from "./client";
import type { SemanticPackage } from "@/types/backend";

export const semanticsApi = {
  package: (databaseId: number) => request<SemanticPackage>(`/semantics/${databaseId}/package`),
};
