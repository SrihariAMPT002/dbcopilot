import { useQuery } from "@tanstack/react-query";
import { BusinessInsightsService } from "@/services/businessInsightsService";

export function useBusinessInsights(databaseId?: number | null) {
  return useQuery({
    queryKey: ["business-insights", databaseId ?? "default"],
    queryFn: () => BusinessInsightsService.list(Number(databaseId ?? 0)),
    enabled: typeof databaseId === "number" && databaseId > 0,
  });
}
