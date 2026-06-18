import { request } from "./client";
import type {
  DataProductsResponse,
  BusinessIntelligenceHealthResponse,
  OpportunityRecommendationsResponse,
  PredictiveReadinessResponse,
  RecommendationsResponse,
  WarehouseDesignsResponse,
} from "@/types/backend";

export const businessIntelligenceApi = {
  generate: (databaseId: number) => request(`/business-intelligence/generate/${databaseId}`, { method: "POST" }),
  opportunities: (databaseId: number) => request<OpportunityRecommendationsResponse>(`/business-intelligence/opportunities/${databaseId}`),
  dataProducts: (databaseId: number) => request<DataProductsResponse>(`/business-intelligence/data-products/${databaseId}`),
  warehouseDesigns: (databaseId: number) => request<WarehouseDesignsResponse>(`/business-intelligence/warehouse-designs/${databaseId}`),
  recommendations: (databaseId: number) => request<RecommendationsResponse>(`/business-intelligence/recommendations/${databaseId}`),
  predictiveReadiness: (databaseId: number) => request<PredictiveReadinessResponse>(`/business-intelligence/predictive-readiness/${databaseId}`),
  health: (databaseId: number) => request<BusinessIntelligenceHealthResponse>(`/business-intelligence/health/${databaseId}`),
};
