import { request } from "./client";
import type { KpiPackage } from "@/types/backend";

export const kpiApi = {
  package: (databaseId: number) => request<KpiPackage>(`/kpi-intelligence/${databaseId}`),
};
