import { useQuery } from "@tanstack/react-query";
import { DashboardService } from "@/services/dashboardService";

export function useDashboard(databaseId?: number | null) {
  return useQuery({
    queryKey: ["dashboard", databaseId ?? "default"],
    queryFn: () => DashboardService.getSummary(databaseId),
    enabled: typeof databaseId === "number" && databaseId > 0,
    staleTime: 60_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: false,
  });
}
