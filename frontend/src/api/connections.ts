import { request } from "./client";
import type { Connection } from "@/types/backend";

export const connectionsApi = {
  list: () => request<Connection[]>("/connections"),
  test: (payload: Record<string, unknown>) => request("/connections/test", { method: "POST", body: JSON.stringify(payload) }),
  create: (payload: Record<string, unknown>) =>
    request("/connections", { method: "POST", body: JSON.stringify(payload) }),
  sync: (dbId: number) =>
    request(`/connections/${dbId}/sync`, { method: "POST" }),
};
