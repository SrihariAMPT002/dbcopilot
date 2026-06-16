import { readinessApi } from "@/api/readiness";

export const ReadinessService = {
  getSnapshot: readinessApi.snapshot,
  getHistory: readinessApi.history,
  getRemediation: readinessApi.remediation,
  recalculate: readinessApi.recalculate,
};
