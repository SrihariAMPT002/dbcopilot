import { useMemo, useState } from "react";
import { History, Filter, ArrowRight } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { EmptyState } from "@/components/empty-state";
import { useDatabaseContext } from "@/context/database-context";
import { useReadinessHistory } from "@/hooks/useReadinessHistory";
import { ReadinessSparkline } from "@/components/readiness/ReadinessSparkline";

export function ReadinessHistoryPage() {
  const { selectedDatabaseId } = useDatabaseContext();
  const dbId = selectedDatabaseId ?? 1;
  const [maturityLevel, setMaturityLevel] = useState<string>("all");
  const [minScore, setMinScore] = useState<string>("");
  const [maxScore, setMaxScore] = useState<string>("");

  const filters = useMemo(
    () => ({
      maturityLevel: maturityLevel === "all" ? null : maturityLevel,
      minScore: minScore ? Number(minScore) : null,
      maxScore: maxScore ? Number(maxScore) : null,
    }),
    [maturityLevel, minScore, maxScore],
  );

  const { data } = useReadinessHistory(dbId, filters);
  const snapshots = data?.snapshots ?? [];
  const trendValues = snapshots.slice(0, 8).map((item) => item.overall_score).reverse();

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Surface"
        title="Readiness history"
        description="Filter persisted readiness snapshots and review maturity progression over time."
        actions={
          <Button asChild variant="outline" size="sm">
            <Link to="/readiness">
              Back to readiness <ArrowRight className="ml-1 h-3.5 w-3.5" />
            </Link>
          </Button>
        }
      />

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0">
          <div className="space-y-1">
            <CardTitle className="text-base">History filters</CardTitle>
            <CardDescription>Filter by maturity level and score range.</CardDescription>
          </div>
          <Badge variant="outline" className="gap-1 text-[11px] uppercase">
            <Filter className="h-3 w-3" />
            {snapshots.length} snapshots
          </Badge>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-4">
          <Select value={maturityLevel} onValueChange={setMaturityLevel}>
            <SelectTrigger>
              <SelectValue placeholder="Maturity level" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All levels</SelectItem>
              <SelectItem value="NOT_READY">Not ready</SelectItem>
              <SelectItem value="PARTIAL">Partial</SelectItem>
              <SelectItem value="READY">Ready</SelectItem>
              <SelectItem value="STALE">Stale</SelectItem>
            </SelectContent>
          </Select>
          <Input type="number" min={0} max={100} placeholder="Min score" value={minScore} onChange={(e) => setMinScore(e.target.value)} />
          <Input type="number" min={0} max={100} placeholder="Max score" value={maxScore} onChange={(e) => setMaxScore(e.target.value)} />
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              setMaturityLevel("all");
              setMinScore("");
              setMaxScore("");
            }}
          >
            Reset filters
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Maturity trend</CardTitle>
          <CardDescription>Score movement for the selected readiness history window.</CardDescription>
        </CardHeader>
        <CardContent>
          {trendValues.length ? (
            <ReadinessSparkline values={trendValues} />
          ) : (
            <EmptyState icon={History} title="No trend data" description="Run readiness recomputation to populate the history view." />
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4">
        {snapshots.length ? (
          snapshots.map((snapshot) => (
            <Card key={snapshot.id}>
              <CardContent className="pt-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-foreground">{snapshot.maturity_level}</div>
                    <div className="text-xs text-muted-foreground">{new Date(snapshot.generated_at).toLocaleString()}</div>
                  </div>
                  <Badge variant="outline" className="tabular-nums">
                    {snapshot.overall_score}
                  </Badge>
                </div>
                <div className="mt-3 text-sm text-muted-foreground">{snapshot.summary ?? "No summary persisted."}</div>
                <div className="mt-3 text-xs text-muted-foreground">
                  Trace: {snapshot.trace_id ?? "n/a"} · Model: {snapshot.model_name ?? "n/a"}
                </div>
              </CardContent>
            </Card>
          ))
        ) : (
          <EmptyState icon={History} title="No snapshots found" description="Try clearing filters or run a readiness recalculation." />
        )}
      </div>
    </div>
  );
}
