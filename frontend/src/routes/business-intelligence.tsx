import { createFileRoute } from "@tanstack/react-router";
import { BusinessIntelligencePage } from "@/pages/BusinessIntelligencePage";

export const Route = createFileRoute("/business-intelligence")({
  component: BusinessIntelligencePage,
});
