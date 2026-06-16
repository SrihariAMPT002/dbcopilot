import { useState } from "react";
import { Search } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useRetrievalSearch } from "@/hooks/useRetrievalSearch";

export function CrossDatabaseSearch() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const { data } = useRetrievalSearch(null, submittedQuery, 5);
  const hits = data?.results ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Cross database search</CardTitle>
        <CardDescription>Search across all indexed knowledge collections.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search across databases..." className="h-9 pl-9" />
          </div>
          <Button size="sm" disabled={!query.trim()} onClick={() => setSubmittedQuery(query.trim())}>
            Search
          </Button>
        </div>
        {hits.length ? (
          <div className="space-y-2">
            {hits.slice(0, 3).map((hit, index) => (
              <div key={`${hit.collection}-${index}`} className="rounded-md border border-border bg-card p-3 text-sm">
                {hit.table_name || hit.collection} · {Math.round(hit.score * 100)}%
              </div>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
