import { businessEventsApi } from "@/api/business-events";

export const BusinessEventsService = {
  list: businessEventsApi.list,
  health: businessEventsApi.health,
};
