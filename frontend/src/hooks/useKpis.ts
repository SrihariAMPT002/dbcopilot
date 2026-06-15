import { useQuery } from "@tanstack/react-query";
import { KPIService } from "@/services/kpiService";

export function useKPIs(databaseId: number) {
  return useQuery({
    queryKey: ["kpi", databaseId],
    queryFn: () => KPIService.getPackage(databaseId),
  });
}
