import { Wand2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
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
      {dbId ? (
        <RerankingPanel databaseId={dbId} />
      ) : (
        <Card className="border-border bg-card shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">No database selected</CardTitle>
            <CardDescription>Select a database to run reranking.</CardDescription>
          </CardHeader>
          <CardContent>
            <EmptyState icon={Wand2} title="Select a database" description="Reranking needs an active database context." />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
