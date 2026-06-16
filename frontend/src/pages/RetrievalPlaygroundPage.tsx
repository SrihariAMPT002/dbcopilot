import { PageHeader } from "@/components/page-header";
import { ActiveDatabaseBadge } from "@/components/common/ActiveDatabaseBadge";
import { useDatabaseContext } from "@/context/database-context";
import { RetrievalPlayground } from "@/components/embeddings/RetrievalPlayground";

export function RetrievalPlaygroundPage() {
  const { selectedDatabaseId } = useDatabaseContext();
  const dbId = selectedDatabaseId ?? 1;

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="AI Surface" title="Retrieval playground" description="Dedicated hybrid retrieval search over the knowledge layer." actions={<ActiveDatabaseBadge />} />
      <RetrievalPlayground databaseId={dbId} />
    </div>
  );
}
