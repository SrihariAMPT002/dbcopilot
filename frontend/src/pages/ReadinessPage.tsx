import { Gauge, ShieldCheck, BookOpenText, Network, TrendingUp, Boxes, Sparkles, Bot, Lightbulb } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CoverageBar } from "@/components/coverage-bar";
import { Button } from "@/components/ui/button";
import { useReadiness } from "@/hooks/useReadiness";

export function ReadinessPage() {
  const dbId = 1;
  const { data } = useReadiness(dbId);
  const scores = [
    { label: "Governance", value: data?.scores.metadata_score ?? 0, icon: ShieldCheck },
    { label: "Semantic", value: data?.scores.semantic_score ?? 0, icon: BookOpenText },
    { label: "Relationship", value: data?.scores.relationship_score ?? 0, icon: Network },
    { label: "KPI", value: data?.scores.kpi_score ?? 0, icon: TrendingUp },
    { label: "Embedding", value: data?.scores.embeddings_score ?? 0, icon: Boxes },
    { label: "Prompt Studio", value: data?.scores.prompt_score ?? 0, icon: Sparkles },
    { label: "Agent", value: data?.scores.overall_score ?? 0, icon: Bot },
  ];
  const overall = data?.scores.overall_score ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="AI Surface" title="AI readiness" description="Composite score across persisted governance, semantic, relationship, KPI, embedding, and prompt packages." />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">Overall readiness</CardTitle>
            <CardDescription>Weighted across all intelligence packages.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-4">
            <div className="relative grid h-44 w-44 place-items-center">
              <svg className="absolute inset-0 -rotate-90" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="44" fill="none" stroke="var(--muted)" strokeWidth="9" />
                <circle
                  cx="50"
                  cy="50"
                  r="44"
                  fill="none"
                  stroke="url(#rg)"
                  strokeWidth="9"
                  strokeLinecap="round"
                  strokeDasharray={`${2 * Math.PI * 44 * (overall / 100)} ${2 * Math.PI * 44}`}
                />
                <defs>
                  <linearGradient id="rg" x1="0" x2="1" y1="0" y2="1">
                    <stop offset="0%" stopColor="var(--primary)" />
                    <stop offset="100%" stopColor="var(--primary-glow)" />
                  </linearGradient>
                </defs>
              </svg>
              <div className="text-center">
                <div className="text-4xl font-semibold tracking-tight text-foreground">{overall}</div>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">readiness</div>
              </div>
            </div>
            <Badge variant="outline" className="gap-1.5 border-[var(--success)]/40 bg-[var(--success)]/10 text-[var(--success)]">
              <Gauge className="h-3 w-3" /> {data?.readiness_status ?? "pending"}
            </Badge>
          </CardContent>
        </Card>
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Per-package scores</CardTitle>
            <CardDescription>Based on persisted package completeness and coverage.</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {scores.map((s) => (
              <div key={s.label} className="rounded-md border border-border bg-card p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <div className="grid h-7 w-7 shrink-0 place-items-center rounded-md bg-gradient-to-br from-primary/15 to-primary/0 text-primary">
                      <s.icon className="h-3.5 w-3.5" />
                    </div>
                    <span className="text-sm font-medium text-foreground">{s.label}</span>
                  </div>
                  <span className="text-sm font-semibold tabular-nums text-foreground">{s.value}</span>
                </div>
                <CoverageBar
                  value={s.value}
                  className="mt-2"
                  tone={s.value >= 80 ? "success" : s.value >= 60 ? "primary" : s.value >= 40 ? "warning" : "danger"}
                />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recommendations</CardTitle>
          <CardDescription>{data?.remediation_hints?.length ? "Generated from package gaps." : "No remediation hints available yet."}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {(data?.remediation_hints ?? []).map((hint) => (
            <div key={hint} className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-3 rounded-md border border-border bg-card p-3">
              <div className="grid h-8 w-8 place-items-center rounded-md bg-primary/10 text-primary">
                <Lightbulb className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <div className="text-sm font-medium text-foreground">Recommendation</div>
                <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>
              </div>
              <Button variant="ghost" size="sm" className="shrink-0 text-xs">
                Resolve
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
