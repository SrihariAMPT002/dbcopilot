import { observabilityApi } from "@/api/observability";

export const ObservabilityService = {
  listTraces: observabilityApi.traces,
  traceDetail: observabilityApi.traceDetail,
  lifecycleEvents: observabilityApi.lifecycleEvents,
};
