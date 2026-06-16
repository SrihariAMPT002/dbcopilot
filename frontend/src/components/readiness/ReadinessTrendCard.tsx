import { ArrowDownRight, ArrowUpRight, Minus, Clock3 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";
import type { ReadinessHistoryItem } from "@/types/backend";
import { ReadinessSparkline } from "./ReadinessSparkline";

type ReadinessTrendCardProps = {
  snapshots: ReadinessHistoryItem[];
};

export function ReadinessTrendCard({ snapshots }: ReadinessTrendCardProps) {
  const recent = snapshots.slice(0, 5);
  const latest = recent[0];
  const previous = recent[1];
  const delta = latest && previous ? latest.overall_score - previous.overall_score : 0;
  const trendLabel = delta > 0 ? "Improving" : delta < 0 ? "Declining" : "Stable";
  const TrendIcon = delta > 0 ? ArrowUpRight : delta < 0 ? ArrowDownRight : Minus;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0">
        <div className="space-y-1">
          <CardTitle className="text-base">Readiness trend</CardTitle>
          <CardDescription>Latest maturity snapshots and score movement over time.</CardDescription>
        </div>
        {latest ? (
          <Badge variant="outline" className="gap-1 text-[11px] uppercase">
            <TrendIcon className="h-3 w-3" />
            {trendLabel}
          </Badge>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3">
        {recent.length ? (
          <>
            <div className="rounded-lg border border-border bg-card p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium text-foreground">Maturity trend</div>
                  <div className="text-xs text-muted-foreground">Latest 5 readiness snapshots</div>
                </div>
                <div className="text-right">
                  <div className="text-lg font-semibold tabular-nums text-foreground">{latest?.overall_score ?? 0}</div>
                  <div className="text-[11px] text-muted-foreground">{latest?.maturity_level ?? "unknown"}</div>
                </div>
              </div>
              <div className="mt-3 text-primary">
                <ReadinessSparkline values={recent.map((item) => item.overall_score).reverse()} />
              </div>
            </div>
            {recent.map((snapshot, index) => {
              const prev = recent[index + 1];
              const change = prev ? snapshot.overall_score - prev.overall_score : 0;
              return (
                <div key={snapshot.id} className="rounded-lg border border-border bg-card p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium text-foreground">{snapshot.maturity_level}</div>
                      <div className="text-xs text-muted-foreground">{new Date(snapshot.generated_at).toLocaleString()}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-semibold tabular-nums text-foreground">{snapshot.overall_score}</div>
                      <div className="text-[11px] text-muted-foreground">
                        {change >= 0 ? "+" : ""}
                        {change} vs previous
                      </div>
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground line-clamp-2">{snapshot.summary ?? "No summary available."}</div>
                </div>
              );
            })}
          </>
        ) : (
          <EmptyState
            icon={Clock3}
            title="No readiness history yet"
            description="Run readiness recompute to generate a maturity trend and snapshot history."
          />
        )}
      </CardContent>
    </Card>
  );
}
