import { useState } from "react";
import { GitBranch, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/empty-state";
import { useRetrievalGraph } from "@/hooks/useRetrievalSearch";

export function GraphExplorer({ databaseId }: { databaseId: number }) {
  const [query, setQuery] = useState("");
  const { data, isFetching } = useRetrievalGraph(databaseId, query, 2, 5);
  const neighbors = data?.neighbors ?? [];
  const paths = data?.shortest_paths ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Graph explorer</CardTitle>
        <CardDescription>Neighbor expansion, shortest paths, contextual retrieval, and lineage traversal.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search graph context..." />
          <Button size="sm" disabled={isFetching || !query.trim()} className="gap-1.5">
            {isFetching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <GitBranch className="h-3.5 w-3.5" />}
            Explore
          </Button>
        </div>
        {neighbors.length || paths.length ? (
          <div className="space-y-3">
            <div>
              <div className="mb-2 text-sm font-medium text-foreground">Neighbors</div>
              <div className="space-y-2">
                {neighbors.slice(0, 5).map((node) => (
                  <div key={`${node.table_id}-${node.depth}`} className="rounded-md border border-border bg-card p-3 text-sm">
                    {node.schema_name}.{node.table_name} · degree {node.degree}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-2 text-sm font-medium text-foreground">Shortest paths</div>
              <div className="space-y-2">
                {paths.slice(0, 5).map((path) => (
                  <div key={`${path.source_table_id}-${path.target_table_id}`} className="rounded-md border border-border bg-card p-3 text-sm">
                    {path.steps.map((step) => `${step.source_table_name} → ${step.target_table_name}`).join(" · ")}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <EmptyState icon={GitBranch} title="No graph results yet" description="Search graph context to inspect lineage and neighbors." />
        )}
      </CardContent>
    </Card>
  );
}
