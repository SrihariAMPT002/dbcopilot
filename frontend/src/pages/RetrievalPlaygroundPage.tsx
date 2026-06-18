import { Search } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
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
      {dbId ? (
        <RetrievalPlayground databaseId={dbId} />
      ) : (
        <Card className="border-border bg-card shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">No database selected</CardTitle>
            <CardDescription>Select a database to run retrieval search.</CardDescription>
          </CardHeader>
          <CardContent>
            <EmptyState icon={Search} title="Select a database" description="Retrieval search needs an active database context." />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
