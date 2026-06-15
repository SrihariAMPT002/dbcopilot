import { createFileRoute } from "@tanstack/react-router";
import { ConnectPage } from "@/pages/ConnectPage";

export const Route = createFileRoute("/connect")({
  head: () => ({ meta: [{ title: "Connect Database — DBCopilot" }] }),
  component: ConnectPage,
});
