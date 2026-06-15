import { request } from "./client";
import type { RelationshipPackage } from "@/types/backend";

export const relationshipsApi = {
  package: (databaseId: number) => request<RelationshipPackage>(`/relationships/${databaseId}`),
};
