import { MetricCard } from "@/components/metric-card";
import { Activity, Database, Search } from "lucide-react";

export function RetrievalMetrics({
  totalDocuments,
  logs,
  evaluations,
}: {
  totalDocuments: number;
  logs: number;
  evaluations: number;
}) {
  return (
    <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <MetricCard label="Knowledge docs" value={String(totalDocuments)} icon={Database} tone="info" />
      <MetricCard label="Retrieval logs" value={String(logs)} icon={Activity} tone="default" />
      <MetricCard label="Evaluations" value={String(evaluations)} icon={Search} tone="success" />
    </section>
  );
}
