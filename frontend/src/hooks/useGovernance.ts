import { useQuery } from "@tanstack/react-query";
import { GovernanceService } from "@/services/governanceService";

export function useGovernance(databaseId?: number | null) {
  return useQuery({
    queryKey: ["governance", databaseId ?? "default"],
    queryFn: () => GovernanceService.getPackages(Number(databaseId ?? 0)),
    enabled: typeof databaseId === "number" && databaseId > 0,
  });
}

export function useGovernanceSummary(databaseId?: number | null) {
  return useQuery({
    queryKey: ["governance-summary", databaseId ?? "default"],
    queryFn: () => GovernanceService.getSummary(Number(databaseId ?? 0)),
    enabled: typeof databaseId === "number" && databaseId > 0,
  });
}

export function useGovernanceEvidence(tableId?: number | null) {
  return useQuery({
    queryKey: ["governance-evidence", tableId],
    queryFn: () => GovernanceService.getEvidence(Number(tableId)),
    enabled: Boolean(tableId),
  });
}
