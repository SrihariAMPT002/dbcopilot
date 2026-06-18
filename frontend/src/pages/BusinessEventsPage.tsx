import { Activity, ArrowRight, Database, ShieldAlert, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { ActiveDatabaseBadge } from "@/components/common/ActiveDatabaseBadge";
import { TraceLink } from "@/components/common/TraceLink";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { Separator } from "@/components/ui/separator";
import { useDatabaseContext } from "@/context/database-context";
import { useBusinessEvents, useBusinessEventsHealth } from "@/hooks/useBusinessEvents";

export function BusinessEventsPage() {
  const { selectedDatabase } = useDatabaseContext();
  const databaseId = selectedDatabase?.database_id ?? null;
  const { data: events, isLoading: eventsLoading, isError: eventsError, error: eventsErr } = useBusinessEvents(databaseId);
  const { data: health, isLoading: healthLoading, isError: healthError, error: healthErr } = useBusinessEventsHealth(databaseId);

  const eventList = events?.events ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Surface"
        title="Business Events"
        description="Traceable lifecycle events inferred from metadata, relationships, and upstream business signals."
        actions={<ActiveDatabaseBadge />}
      />

      {healthLoading || eventsLoading ? (
        <Card className="border-border bg-card shadow-sm">
          <CardContent className="p-6 text-sm text-muted-foreground">Loading business event lineage and history...</CardContent>
        </Card>
      ) : healthError || eventsError ? (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardHeader>
            <CardTitle className="text-base text-destructive">Business events unavailable</CardTitle>
            <CardDescription>
              {(healthErr instanceof Error && healthErr.message) ||
                (eventsErr instanceof Error && eventsErr.message) ||
                "Failed to load business events for the selected database."}
            </CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card className="border-border bg-card shadow-sm">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Event rows</div>
            <div className="mt-2 text-2xl font-semibold text-foreground">{health?.event_rows ?? eventList.length}</div>
          </CardContent>
        </Card>
        <Card className="border-border bg-card shadow-sm">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Latest trace</div>
            <div className="mt-2 truncate text-2xl font-semibold text-foreground">{health?.latest_trace_id ?? "n/a"}</div>
          </CardContent>
        </Card>
        <Card className="border-border bg-card shadow-sm">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">State</div>
            <div className="mt-2 text-2xl font-semibold text-foreground">{health?.state ?? "unknown"}</div>
          </CardContent>
        </Card>
        <Card className="border-border bg-card shadow-sm">
          <CardContent className="p-4">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Database</div>
            <div className="mt-2 text-2xl font-semibold text-foreground">{selectedDatabase?.database_name ?? "n/a"}</div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card className="border-border bg-card shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">Event history</CardTitle>
            <CardDescription>Incremental history of detected business events with traceability.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {!eventList.length ? (
              <EmptyState icon={Activity} title="No business events yet" description="Run sync to detect lifecycle events and build history over time." />
            ) : (
              eventList.map((event) => (
                <div key={event.id} className="rounded-2xl border border-border bg-card p-4 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-foreground">{event.event_name}</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {event.event_type ?? "unknown"} · Confidence {Math.round((event.confidence_score ?? 0) * 100)}%
                      </div>
                    </div>
                    <Badge variant="outline" className="text-[10px] uppercase">
                      {event.event_type ?? "event"}
                    </Badge>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(event.source_tables ?? []).map((table) => (
                      <Badge key={table} variant="secondary" className="text-[10px]">
                        {table}
                      </Badge>
                    ))}
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                    <span>Created {event.created_at ? new Date(event.created_at).toLocaleString() : "n/a"}</span>
                    <TraceLink traceId={event.trace_id} label="Open trace" className="text-[11px]" />
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="border-border bg-card shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">Lineage evidence</CardTitle>
            <CardDescription>Source tables and causal hints used during detection.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {eventList.length ? (
              eventList.slice(0, 3).map((event, index) => (
                <div key={`${event.id}-${index}`} className="rounded-2xl border border-border bg-background p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium text-foreground">{event.event_name}</div>
                    <Badge variant="outline" className="text-[10px] uppercase">
                      {index === 0 ? "latest" : "historic"}
                    </Badge>
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    This event is linked to {event.source_tables?.length ?? 0} source table(s) and persisted with trace-aware metadata.
                  </div>
                  <Separator className="my-3" />
                  <div className="flex flex-wrap gap-2">
                    {(event.source_tables ?? []).length ? (
                      event.source_tables.map((table) => (
                        <Badge key={`${event.id}-${table}`} variant="outline" className="text-[10px]">
                          {table}
                        </Badge>
                      ))
                    ) : (
                      <Badge variant="outline" className="text-[10px]">
                        No source tables
                      </Badge>
                    )}
                  </div>
                  <div className="mt-3 flex items-center gap-2 text-[11px] text-muted-foreground">
                    <Sparkles className="h-3.5 w-3.5" />
                    Causal chain is inferred from table names, relation edges, and incremental detection history.
                  </div>
                </div>
              ))
            ) : (
              <EmptyState icon={Database} title="No lineage evidence yet" description="As events are detected, this panel will show source tables and trace links." />
            )}
            <div className="rounded-2xl border border-dashed border-border bg-muted/20 p-4 text-xs text-muted-foreground">
              <div className="flex items-center gap-2 font-medium text-foreground">
                <ShieldAlert className="h-4 w-4" />
                Incremental history
              </div>
              <div className="mt-2">
                New event signatures are appended over time while duplicate signatures are skipped, so recomputes preserve change history instead of overwriting it.
              </div>
              <div className="mt-3 flex items-center gap-2 text-[11px] text-primary">
                Open this module from the sidebar to inspect live history <ArrowRight className="h-3 w-3" />
              </div>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
