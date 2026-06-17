import { useQuery } from "@tanstack/react-query";
import { ObservabilityService } from "@/services/observabilityService";

export function useObservabilityTraces(
  databaseId?: number | null,
  filters?: { module?: string; model_name?: string; trace_id?: string; from_date?: string; to_date?: string },
) {
  return useQuery({
    queryKey: ["observability-traces", databaseId ?? "default", filters ?? {}],
    queryFn: () => ObservabilityService.listTraces(Number(databaseId ?? 0), filters),
    enabled: typeof databaseId === "number" && databaseId > 0,
    staleTime: 30_000,
    refetchInterval: 30_000,
    refetchOnWindowFocus: false,
  });
}

export function useObservabilityTraceDetail(databaseId?: number | null, traceId?: string | null) {
  return useQuery({
    queryKey: ["observability-trace-detail", databaseId ?? "default", traceId ?? "none"],
    queryFn: () => ObservabilityService.traceDetail(Number(databaseId ?? 0), traceId ?? ""),
    enabled: typeof databaseId === "number" && databaseId > 0 && !!traceId,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}

export function useLifecycleEvents(databaseId?: number | null) {
  return useQuery({
    queryKey: ["observability-lifecycle-events", databaseId ?? "default"],
    queryFn: () => ObservabilityService.lifecycleEvents(Number(databaseId ?? 0)),
    enabled: typeof databaseId === "number" && databaseId > 0,
    staleTime: 60_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: false,
  });
}
