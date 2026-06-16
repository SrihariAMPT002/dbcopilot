import { useQuery } from "@tanstack/react-query";
import { DashboardService } from "@/services/dashboardService";

export function useDashboard(databaseId?: number | null) {
  return useQuery({
    queryKey: ["dashboard", databaseId ?? "default"],
    queryFn: () => DashboardService.getSummary(databaseId),
  });
}
