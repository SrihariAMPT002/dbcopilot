import { readinessApi } from "@/api/readiness";

export const ReadinessService = {
  getSnapshot: readinessApi.snapshot,
};
