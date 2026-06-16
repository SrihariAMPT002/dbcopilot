import { request } from "./client";
import type { Connection, ConnectionLifecycleDeleteRequest, ConnectionLifecycleResponse } from "@/types/backend";

export const connectionsApi = {
  list: () => request<Connection[]>("/connections"),
  test: (payload: Record<string, unknown>) => request("/connections/test", { method: "POST", body: JSON.stringify(payload) }),
  create: (payload: Record<string, unknown>) =>
    request("/connections", { method: "POST", body: JSON.stringify(payload) }),
  sync: (dbId: number) =>
    request(`/connections/${dbId}/sync`, { method: "POST" }),
  disconnect: (dbId: number, payload: Record<string, unknown>) =>
    request<ConnectionLifecycleResponse>(`/connections/${dbId}/disconnect`, { method: "POST", body: JSON.stringify(payload) }),
  reconnect: (dbId: number, payload: Record<string, unknown>) =>
    request<ConnectionLifecycleResponse>(`/connections/${dbId}/reconnect`, { method: "POST", body: JSON.stringify(payload) }),
  archive: (dbId: number, payload: Record<string, unknown>) =>
    request<ConnectionLifecycleResponse>(`/connections/${dbId}/archive`, { method: "POST", body: JSON.stringify(payload) }),
  restore: (dbId: number, payload: Record<string, unknown>) =>
    request<ConnectionLifecycleResponse>(`/connections/${dbId}/restore`, { method: "POST", body: JSON.stringify(payload) }),
  delete: (dbId: number, payload?: ConnectionLifecycleDeleteRequest) =>
    request<ConnectionLifecycleResponse>(`/connections/${dbId}`, {
      method: "DELETE",
      body: JSON.stringify(payload ?? {}),
    }),
};
