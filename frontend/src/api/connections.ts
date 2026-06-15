import { request } from "./client";
import type { Connection } from "@/types/backend";

export const connectionsApi = {
  list: () => request<Connection[]>("/connections"),
};
