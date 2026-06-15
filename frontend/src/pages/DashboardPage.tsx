import { Link } from "@tanstack/react-router";
import { Database, Activity, CheckCircle2, XCircle, ShieldCheck, BookOpenText, Network, TrendingUp, Boxes, Sparkles, ArrowRight, RefreshCw, Play } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { StatusBadge, type StatusKind } from "@/components/status-badge";
import { CoverageBar } from "@/components/coverage-bar";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

const coverage = [
  { label: "Governance", value: 86, icon: ShieldCheck, to: "/governance" },
  { label: "Semantics", value: 72, icon: BookOpenText, to: "/semantics" },
  { label: "Relationships", value: 64, icon: Network, to: "/relationships" },
  { label: "KPI", value: 58, icon: TrendingUp, to: "/kpi" },
  { label: "Embeddings", value: 91, icon: Boxes, to: "/embeddings" },
  { label: "Prompt Studio", value: 48, icon: Sparkles, to: "/prompt-studio" },
] as const;

const activity: { time: string; title: string; meta: string; status: StatusKind }[] = [
  { time: "2m ago", title: "Governance package regenerated", meta: "warehouse_prod · 142 tables", status: "success" },
  { time: "11m ago", title: "Embedding sync completed", meta: "qdrant · 18.4k vectors upserted", status: "success" },
  { time: "34m ago", title: "Relationship intelligence job running", meta: "crm_replica · cluster discovery", status: "running" },
  { time: "1h ago", title: "KPI extraction failed", meta: "finance_dw · timeout on lineage walker", status: "failed" },
  { time: "3h ago", title: "Metadata sync queued", meta: "events_lake · scheduled", status: "queued" },
];

const pipeline = [
  { stage: "Metadata sync", value: 100, status: "success" as StatusKind },
  { stage: "Governance", value: 86, status: "success" as StatusKind },
  { stage: "Semantics", value: 72, status: "running" as StatusKind },
  { stage: "Relationships", value: 64, status: "running" as StatusKind },
  { stage: "KPI", value: 58, status: "queued" as StatusKind },
  { stage: "Embeddings", value: 91, status: "success" as StatusKind },
  { stage: "Prompt Studio", value: 48, status: "queued" as StatusKind },
];

export function DashboardPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Overview"
        title="Platform dashboard"
        description="Real-time health of metadata sync, AI intelligence generation, and downstream agent readiness."
        actions={<><Button variant="outline" size="sm" className="gap-1.5"><RefreshCw className="h-3.5 w-3.5" /> Refresh</Button><Button size="sm" className="gap-1.5 bg-gradient-to-br from-primary to-primary-glow text-primary-foreground shadow-[var(--shadow-glow)] hover:opacity-95"><Play className="h-3.5 w-3.5" /> Run pipeline</Button></>}
      />
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Connected databases" value="7" hint="3 production · 4 staging" icon={Database} tone="info" />
        <MetricCard label="Running jobs" value="4" hint="2 sync · 2 AI" icon={Activity} tone="default" trend={{ value: "+2", positive: true }} />
        <MetricCard label="Completed (24h)" value="142" hint="98.6% success rate" icon={CheckCircle2} tone="success" trend={{ value: "+12%", positive: true }} />
        <MetricCard label="Failed (24h)" value="2" hint="Timeout · KPI extractor" icon={XCircle} tone="danger" trend={{ value: "-1", positive: true }} />
      </section>
      <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0">
            <div className="space-y-1"><CardTitle className="text-base">Intelligence coverage</CardTitle><CardDescription>Per-package coverage across all connected sources.</CardDescription></div>
            <Badge variant="outline" className="border-border text-[11px] text-muted-foreground">last refreshed 2 min ago</Badge>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {coverage.map((c) => (
              <Link key={c.label} to={c.to} className="group flex items-center gap-3 rounded-lg border border-border bg-card p-3 transition hover:border-primary/40 hover:shadow-[var(--shadow-md)]">
                <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-primary/15 to-primary/0 text-primary"><c.icon className="h-4 w-4" /></div>
                <div className="min-w-0 flex-1"><div className="flex items-center justify-between gap-2 text-sm"><span className="truncate font-medium text-foreground">{c.label}</span><span className="tabular-nums text-muted-foreground">{c.value}%</span></div><CoverageBar value={c.value} className="mt-1.5" /></div>
                <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition group-hover:opacity-100" />
              </Link>
            ))}
          </CardContent>
        </Card>
        <Card><CardHeader><CardTitle className="text-base">AI Readiness</CardTitle><CardDescription>Composite score across all intelligence packages.</CardDescription></CardHeader><CardContent className="space-y-4"><div className="relative mx-auto grid h-40 w-40 place-items-center"><svg className="absolute inset-0 -rotate-90" viewBox="0 0 100 100"><circle cx="50" cy="50" r="44" fill="none" stroke="var(--muted)" strokeWidth="8" /><circle cx="50" cy="50" r="44" fill="none" stroke="url(#g1)" strokeWidth="8" strokeLinecap="round" strokeDasharray={`${2 * Math.PI * 44 * 0.74} ${2 * Math.PI * 44}`} /><defs><linearGradient id="g1" x1="0" x2="1" y1="0" y2="1"><stop offset="0%" stopColor="var(--primary)" /><stop offset="100%" stopColor="var(--primary-glow)" /></linearGradient></defs></svg><div className="text-center"><div className="text-3xl font-semibold tracking-tight text-foreground">74</div><div className="text-[10px] uppercase tracking-wider text-muted-foreground">Ready</div></div></div><Separator /><ul className="space-y-2 text-xs"><li className="flex items-center justify-between"><span className="text-muted-foreground">Governance</span><span className="font-medium tabular-nums text-foreground">86</span></li><li className="flex items-center justify-between"><span className="text-muted-foreground">Semantics</span><span className="font-medium tabular-nums text-foreground">72</span></li><li className="flex items-center justify-between"><span className="text-muted-foreground">Agent context</span><span className="font-medium tabular-nums text-foreground">68</span></li></ul><Button asChild variant="outline" size="sm" className="w-full"><Link to="/readiness">View full report <ArrowRight className="ml-1 h-3.5 w-3.5" /></Link></Button></CardContent></Card>
      </section>
      <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2"><CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0"><div className="space-y-1"><CardTitle className="text-base">Pipeline health</CardTitle><CardDescription>Current execution across the intelligence pipeline.</CardDescription></div><Button asChild variant="ghost" size="sm" className="text-xs"><Link to="/jobs">Open jobs <ArrowRight className="ml-1 h-3 w-3" /></Link></Button></CardHeader><CardContent><ol className="relative">{pipeline.map((p, i) => (<li key={p.stage} className="grid grid-cols-[24px_minmax(0,1fr)_auto] items-center gap-3 py-2.5"><div className="relative grid place-items-center"><div className="h-2 w-2 rounded-full bg-primary shadow-[0_0_0_4px_var(--background),0_0_0_5px_var(--border)]" />{i !== pipeline.length - 1 && (<div className="absolute top-3 h-[26px] w-px bg-border" />)}</div><div className="min-w-0"><div className="flex items-center gap-2 text-sm"><span className="truncate font-medium text-foreground">{p.stage}</span></div><CoverageBar value={p.value} className="mt-1" /></div><StatusBadge status={p.status} /></li>))}</ol></CardContent></Card>
        <Card><CardHeader><CardTitle className="text-base">Recent activity</CardTitle><CardDescription>Latest jobs and platform events.</CardDescription></CardHeader><CardContent className="space-y-3">{activity.map((a, i) => (<div key={i} className="flex items-start gap-3 border-b border-border pb-3 last:border-none last:pb-0"><div className="mt-0.5"><StatusBadge status={a.status} /></div><div className="min-w-0 flex-1"><div className="truncate text-sm font-medium text-foreground">{a.title}</div><div className="truncate text-xs text-muted-foreground">{a.meta}</div></div><span className="shrink-0 text-[11px] text-muted-foreground">{a.time}</span></div>))}</CardContent></Card>
      </section>
    </div>
  );
}
