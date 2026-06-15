import { request } from "./client";
import type { HealthResponse } from "@/types/backend";

export const healthApi = {
  health: () => request<HealthResponse>("/health"),
};
