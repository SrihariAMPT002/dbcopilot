import { businessIntelligenceApi } from "@/api/business-intelligence";

export const BusinessIntelligenceService = {
  generate: businessIntelligenceApi.generate,
  opportunities: businessIntelligenceApi.opportunities,
  dataProducts: businessIntelligenceApi.dataProducts,
  warehouseDesigns: businessIntelligenceApi.warehouseDesigns,
  recommendations: businessIntelligenceApi.recommendations,
  predictiveReadiness: businessIntelligenceApi.predictiveReadiness,
  health: businessIntelligenceApi.health,
};
