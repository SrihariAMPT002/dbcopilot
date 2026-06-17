import { PageHeader } from "@/components/page-header";
import { ActiveDatabaseBadge } from "@/components/common/ActiveDatabaseBadge";
import { useDatabaseContext } from "@/context/database-context";
import { RerankingPanel } from "@/components/embeddings/RerankingPanel";

export function RerankingPage() {
  const { selectedDatabase } = useDatabaseContext();
  const dbId = selectedDatabase?.database_id ?? null;

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="AI Surface" title="Reranking" description="LLM reranking with persisted trace and evaluation outputs." actions={<ActiveDatabaseBadge />} />
      <RerankingPanel databaseId={dbId} />
    </div>
  );
}
