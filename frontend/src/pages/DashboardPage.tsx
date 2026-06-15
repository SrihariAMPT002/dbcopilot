import { Database, Activity, CheckCircle2, XCircle, ShieldCheck, BookOpenText, Network, TrendingUp, Boxes, Sparkles, ArrowRight, RefreshCw, Play } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { StatusBadge, type StatusKind } from "@/components/status-badge";
import { CoverageBar } from "@/components/coverage-bar";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { EmptyState } from "@/components/empty-state";
import { ActiveDatabaseBadge } from "@/components/common/ActiveDatabaseBadge";

const coverage: { label: string; value: number; icon: typeof ShieldCheck; to: string }[] = [];
const activity: { time: string; title: string; meta: string; status: StatusKind }[] = [];
const pipeline: { stage: string; value: number; status: StatusKind }[] = [];

export function DashboardPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="DBCopilot"
        title="Platform dashboard"
        description="Real-time health of metadata sync, AI intelligence generation, and downstream agent readiness."
        actions={
          <>
            <ActiveDatabaseBadge />
            <Button variant="outline" size="sm" className="gap-1.5">
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </Button>
            <Button size="sm" className="gap-1.5 bg-gradient-to-br from-primary to-primary-glow text-primary-foreground shadow-[var(--shadow-glow)] hover:opacity-95">
              <Play className="h-3.5 w-3.5" /> Run pipeline
            </Button>
          </>
        }
      />
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Connected databases" value="0" hint="No active sources loaded" icon={Database} tone="info" />
        <MetricCard label="Running jobs" value="0" hint="Waiting for backend activity" icon={Activity} tone="default" />
        <MetricCard label="Completed (24h)" value="0" hint="No runs yet" icon={CheckCircle2} tone="success" />
        <MetricCard label="Failed (24h)" value="0" hint="No failures yet" icon={XCircle} tone="danger" />
      </section>
      <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0">
            <div className="space-y-1">
              <CardTitle className="text-base">Intelligence coverage</CardTitle>
              <CardDescription>Per-package coverage across all connected sources.</CardDescription>
            </div>
            <Badge variant="outline" className="border-border text-[11px] text-muted-foreground">
              waiting for data
            </Badge>
          </CardHeader>
          <CardContent className="space-y-4">
            {coverage.length ? (
              coverage.map((c) => (
                <Link key={c.label} to={c.to} className="group flex items-center gap-3 rounded-lg border border-border bg-card p-3 transition hover:border-primary/40 hover:shadow-[var(--shadow-md)]">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-primary/15 to-primary/0 text-primary">
                    <c.icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2 text-sm">
                      <span className="truncate font-medium text-foreground">{c.label}</span>
                      <span className="tabular-nums text-muted-foreground">{c.value}%</span>
                    </div>
                    <CoverageBar value={c.value} className="mt-1.5" />
                  </div>
                  <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition group-hover:opacity-100" />
                </Link>
              ))
            ) : (
              <EmptyState
                icon={Sparkles}
                title="No intelligence packages yet"
                description="Connect a database and run sync to populate governance, semantics, relationships, KPI, and embeddings."
              />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">AI Readiness</CardTitle>
            <CardDescription>Composite score across all intelligence packages.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="relative mx-auto grid h-40 w-40 place-items-center">
              <svg className="absolute inset-0 -rotate-90" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="44" fill="none" stroke="var(--muted)" strokeWidth="8" />
              </svg>
              <div className="text-center">
                <div className="text-3xl font-semibold tracking-tight text-foreground">0</div>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Ready</div>
              </div>
            </div>
            <Separator />
            <ul className="space-y-2 text-xs">
              <li className="flex items-center justify-between">
                <span className="text-muted-foreground">Governance</span>
                <span className="font-medium tabular-nums text-foreground">0</span>
              </li>
              <li className="flex items-center justify-between">
                <span className="text-muted-foreground">Semantics</span>
                <span className="font-medium tabular-nums text-foreground">0</span>
              </li>
              <li className="flex items-center justify-between">
                <span className="text-muted-foreground">Agent context</span>
                <span className="font-medium tabular-nums text-foreground">0</span>
              </li>
            </ul>
            <Button asChild variant="outline" size="sm" className="w-full">
              <Link to="/readiness">
                View full report <ArrowRight className="ml-1 h-3.5 w-3.5" />
              </Link>
            </Button>
          </CardContent>
        </Card>
      </section>
      <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0">
            <div className="space-y-1">
              <CardTitle className="text-base">Pipeline health</CardTitle>
              <CardDescription>Current execution across the intelligence pipeline.</CardDescription>
            </div>
            <Button asChild variant="ghost" size="sm" className="text-xs">
              <Link to="/jobs">
                Open jobs <ArrowRight className="ml-1 h-3 w-3" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {pipeline.length ? (
              <ol className="relative">
                {pipeline.map((p, i) => (
                  <li key={p.stage} className="grid grid-cols-[24px_minmax(0,1fr)_auto] items-center gap-3 py-2.5">
                    <div className="relative grid place-items-center">
                      <div className="h-2 w-2 rounded-full bg-primary shadow-[0_0_0_4px_var(--background),0_0_0_5px_var(--border)]" />
                      {i !== pipeline.length - 1 && <div className="absolute top-3 h-[26px] w-px bg-border" />}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 text-sm">
                        <span className="truncate font-medium text-foreground">{p.stage}</span>
                      </div>
                      <CoverageBar value={p.value} className="mt-1" />
                    </div>
                    <StatusBadge status={p.status} />
                  </li>
                ))}
              </ol>
            ) : (
              <EmptyState
                icon={Activity}
                title="No pipeline activity"
                description="Pipeline status will appear here after the first backend sync."
              />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent activity</CardTitle>
            <CardDescription>Latest jobs and platform events.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {activity.length ? (
              activity.map((a, i) => (
                <div key={i} className="flex items-start gap-3 border-b border-border pb-3 last:border-none last:pb-0">
                  <div className="mt-0.5">
                    <StatusBadge status={a.status} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-foreground">{a.title}</div>
                    <div className="truncate text-xs text-muted-foreground">{a.meta}</div>
                  </div>
                  <span className="shrink-0 text-[11px] text-muted-foreground">{a.time}</span>
                </div>
              ))
            ) : (
              <EmptyState icon={Activity} title="No recent activity" description="Activity will populate once jobs start running." />
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
