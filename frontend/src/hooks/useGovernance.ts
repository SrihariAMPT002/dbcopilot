import { useQuery } from "@tanstack/react-query";
import { GovernanceService } from "@/services/governanceService";

export function useGovernance(databaseId: number) {
  return useQuery({
    queryKey: ["governance", databaseId],
    queryFn: () => GovernanceService.getPackages(databaseId),
  });
}

export function useGovernanceSummary(databaseId: number) {
  return useQuery({
    queryKey: ["governance-summary", databaseId],
    queryFn: () => GovernanceService.getSummary(databaseId),
  });
}
