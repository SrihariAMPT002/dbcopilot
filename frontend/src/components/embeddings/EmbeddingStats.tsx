import { Boxes, Cpu, FileText } from "lucide-react";
import { MetricCard } from "@/components/metric-card";

export function EmbeddingStats({
  collections,
  indexedTables,
  vectorsTotal,
  embeddingModel,
  embeddingCoverage,
}: {
  collections: number;
  indexedTables: number;
  vectorsTotal: number;
  embeddingModel?: string | null;
  embeddingCoverage: number;
}) {
  return (
    <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <MetricCard label="Collections" value={String(collections)} icon={Boxes} tone="info" />
      <MetricCard label="Documents indexed" value={String(indexedTables)} icon={FileText} tone="default" />
      <MetricCard label="Vectors" value={String(vectorsTotal)} hint={`model: ${embeddingModel ?? "n/a"}`} icon={Cpu} tone="success" />
      <MetricCard label="Embedding coverage" value={`${embeddingCoverage}%`} icon={Boxes} progress={embeddingCoverage} tone="success" />
    </section>
  );
}
