import { useQuery } from "@tanstack/react-query";
import { DashboardService } from "@/services/dashboardService";
import { queryKeys } from "@/lib/query-keys";

export function useDashboard(databaseId?: number | null) {
  return useQuery({
    queryKey: queryKeys.dashboard(databaseId ?? "default"),
    queryFn: () => DashboardService.getSummary(databaseId),
    enabled: typeof databaseId === "number" && databaseId > 0,
    staleTime: 60_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: false,
  });
}
