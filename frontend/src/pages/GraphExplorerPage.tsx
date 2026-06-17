import { PageHeader } from "@/components/page-header";
import { ActiveDatabaseBadge } from "@/components/common/ActiveDatabaseBadge";
import { useDatabaseContext } from "@/context/database-context";
import { GraphExplorer } from "@/components/embeddings/GraphExplorer";

export function GraphExplorerPage() {
  const { selectedDatabase } = useDatabaseContext();
  const dbId = selectedDatabase?.database_id ?? null;

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="AI Surface" title="Graph explorer" description="Graph retrieval, lineage traversal, and contextual neighborhood exploration." actions={<ActiveDatabaseBadge />} />
      <GraphExplorer databaseId={dbId} />
    </div>
  );
}
