import { request } from "./client";
import type { GovernanceEvidence, GovernancePackage, GovernanceSummary } from "@/types/backend";

export const governanceApi = {
  packages: (databaseId: number) => request<{ packages: GovernancePackage[] }>(`/governance/packages/${databaseId}`),
  summary: (databaseId: number) => request<GovernanceSummary>(`/governance/pii-summary/${databaseId}`),
  evidence: (tableId: number) => request<GovernanceEvidence>(`/governance/evidence/${tableId}`),
};
