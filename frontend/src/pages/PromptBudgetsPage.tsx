import { Link } from "@tanstack/react-router";
import { ArrowLeft, Gauge, TriangleAlert, ShieldCheck } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { usePromptBudgets } from "@/hooks/usePromptBudgets";

export function PromptBudgetsPage() {
  const { data } = usePromptBudgets();
  const prompts = data?.prompts ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Admin"
        title="Prompt budgets"
        description="Audit prompt budgets, truncation risk, and quality scores across GPT-5 Nano workloads."
        actions={
          <Button asChild variant="outline" size="sm">
            <Link to="/settings">
              <ArrowLeft className="mr-1 h-3.5 w-3.5" />
              Back to settings
            </Link>
          </Button>
        }
      />
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Metric label="Total prompts" value={String(data?.total ?? 0)} icon={Gauge} />
        <Metric label="High risk" value={String(prompts.filter((p) => p.truncation_risk === "high").length)} icon={TriangleAlert} />
        <Metric label="Healthy prompts" value={String(prompts.filter((p) => p.prompt_quality_score >= 80).length)} icon={ShieldCheck} />
      </section>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Prompt audit</CardTitle>
          <CardDescription>Current completion budgets and truncation risk by prompt.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {prompts.length ? (
            prompts.map((prompt) => (
              <div key={prompt.prompt_path} className="rounded-lg border border-border bg-card p-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-foreground">{prompt.prompt_id}</div>
                    <div className="text-xs text-muted-foreground">{prompt.prompt_path}</div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline">Limit {prompt.current_token_limit}</Badge>
                    <Badge variant={prompt.truncation_risk === "high" ? "destructive" : "outline"}>{prompt.truncation_risk} risk</Badge>
                    <Badge variant="outline">Quality {prompt.prompt_quality_score}</Badge>
                  </div>
                </div>
                <div className="mt-2 text-xs text-muted-foreground">
                  Recommended limit: {prompt.recommended_token_limit} · Version: {prompt.version} · Category: {prompt.category}
                </div>
                {prompt.description ? <div className="mt-2 text-xs text-muted-foreground">{prompt.description}</div> : null}
              </div>
            ))
          ) : (
            <EmptyState icon={TriangleAlert} title="No prompts found" description="Prompt budget audit data is unavailable." />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Metric({ label, value, icon: Icon }: { label: string; value: string; icon: typeof Gauge }) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-3">
        <div className="grid h-9 w-9 place-items-center rounded-md bg-primary/10 text-primary">
          <Icon className="h-4 w-4" />
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
          <div className="text-lg font-semibold text-foreground">{value}</div>
        </div>
      </div>
    </Card>
  );
}
