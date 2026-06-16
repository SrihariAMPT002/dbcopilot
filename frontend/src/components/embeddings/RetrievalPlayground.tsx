import { useState } from "react";
import { Search, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/empty-state";
import { useRetrievalSearch } from "@/hooks/useRetrievalSearch";

export function RetrievalPlayground({ databaseId }: { databaseId: number }) {
  const [query, setQuery] = useState("");
  const { data, isFetching } = useRetrievalSearch(databaseId, query, 5);
  const hits = data?.results ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Retrieval playground</CardTitle>
        <CardDescription>Hybrid search over persisted knowledge documents.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search retrieved knowledge..." />
          <Button size="sm" disabled={isFetching || !query.trim()} className="gap-1.5">
            {isFetching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
            Search
          </Button>
        </div>
        {hits.length ? (
          <div className="space-y-2">
            {hits.map((hit, index) => (
              <div key={`${hit.collection}-${index}`} className="rounded-md border border-border bg-card p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-medium text-foreground">{hit.table_name || hit.collection}</div>
                  <div className="text-xs text-muted-foreground">{Math.round(hit.score * 100)}%</div>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">{hit.schema_name || "n/a"}</div>
                <div className="mt-2 line-clamp-3 text-sm text-muted-foreground">{hit.content}</div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState icon={Search} title="No retrieval results yet" description="Run a search to inspect hybrid retrieval output." />
        )}
      </CardContent>
    </Card>
  );
}
