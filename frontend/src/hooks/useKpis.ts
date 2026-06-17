import { useQuery } from "@tanstack/react-query";
import { KPIService } from "@/services/kpiService";

export function useKPIs(databaseId?: number | null) {
  return useQuery({
    queryKey: ["kpi", databaseId ?? "default"],
    queryFn: () => KPIService.getPackage(Number(databaseId ?? 0)),
    enabled: typeof databaseId === "number" && databaseId > 0,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}
