import { request } from "./client";
import type { PipelineJob } from "@/types/backend";

export const jobsApi = {
  list: (limit = 20) => request<PipelineJob[]>(`/pipeline/jobs?limit=${limit}`),
};
