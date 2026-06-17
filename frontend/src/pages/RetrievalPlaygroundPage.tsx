import { PageHeader } from "@/components/page-header";
import { ActiveDatabaseBadge } from "@/components/common/ActiveDatabaseBadge";
import { useDatabaseContext } from "@/context/database-context";
import { RetrievalPlayground } from "@/components/embeddings/RetrievalPlayground";

export function RetrievalPlaygroundPage() {
  const { selectedDatabase } = useDatabaseContext();
  const dbId = selectedDatabase?.database_id ?? null;

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="AI Surface" title="Retrieval playground" description="Dedicated hybrid retrieval search over the knowledge layer." actions={<ActiveDatabaseBadge />} />
      <RetrievalPlayground databaseId={dbId} />
    </div>
  );
}
