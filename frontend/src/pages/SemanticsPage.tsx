import { useMemo, useState } from "react";
import { BookOpenText, Building2, Workflow, Sparkles, Search, Activity } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { useSemantics, useSemanticEvidence } from "@/hooks/useSemantics";
import { useDatabaseContext } from "@/context/database-context";
import { TraceLink } from "@/components/common/TraceLink";

export function SemanticsPage() {
  const { selectedDatabaseId } = useDatabaseContext();
  const dbId = selectedDatabaseId ?? 1;
  const { data } = useSemantics(dbId);
  const { data: evidence } = useSemanticEvidence(dbId);
  const [search, setSearch] = useState("");

  const entities = data?.business_entities ?? [];
  const processes = data?.business_processes ?? [];
  const capabilities = data?.business_capabilities ?? [];
  const glossary = data?.business_glossary ?? [];

  const filteredGlossary = useMemo(
    () =>
      glossary.filter((item) =>
        `${item.term} ${item.definition}`.toLowerCase().includes(search.toLowerCase()),
      ),
    [glossary, search],
  );

  const domainScores = evidence?.domain_scores ?? data?.domain_scores ?? {};
  const evidenceRows = evidence?.evidence ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Intelligence"
        title="Semantics"
        description="Business domain, entities, processes, capabilities, glossary, and semantic evidence from persisted semantic packages."
      />
      <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2 overflow-hidden">
          <div className="relative">
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-transparent" />
            <CardHeader className="relative">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
                  <Building2 className="mr-1 h-3 w-3" /> Domain
                </Badge>
                <Badge variant="outline" className="text-[11px]">
                  {data?.business_domain ?? evidence?.business_domain ?? "Pending discovery"}
                </Badge>
                <Badge variant="outline" className="text-[11px]">
                  <Activity className="mr-1 h-3 w-3" />
                  {Math.round((evidence?.confidence_score ?? data?.confidence_score ?? 0) * 100)}%
                </Badge>
              </div>
              <CardTitle className="text-base">Business summary</CardTitle>
              <CardDescription>{data?.semantic_summary ?? "No semantic summary available yet for this database."}</CardDescription>
            </CardHeader>
          </div>
          <CardContent className="space-y-4 pt-0">
            <section className="space-y-2">
              <div className="text-sm font-semibold text-foreground">Business entities</div>
              <div className="flex flex-wrap gap-2">
                {entities.length ? entities.map((e) => (
                  <Badge key={e} variant="outline" className="gap-1 rounded-full border-border bg-card px-2.5 py-1 text-xs">
                    <Sparkles className="h-3 w-3 text-primary" /> {e}
                  </Badge>
                )) : <div className="text-sm text-muted-foreground">No semantic entities found yet.</div>}
              </div>
            </section>
            <section className="space-y-2">
              <div className="text-sm font-semibold text-foreground">Business processes</div>
              {processes.length ? processes.map((p) => (
                <div key={p} className="rounded-md border border-border bg-card p-3">
                  <div className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
                    <Workflow className="h-4 w-4 text-primary" /> {p}
                  </div>
                </div>
              )) : <div className="text-sm text-muted-foreground">No semantic processes found yet.</div>}
            </section>
            <section className="space-y-2">
              <div className="text-sm font-semibold text-foreground">Business capabilities</div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {capabilities.length ? capabilities.map((c) => (
                  <div key={c} className="rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground">{c}</div>
                )) : <div className="text-sm text-muted-foreground">No capabilities found yet.</div>}
              </div>
            </section>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Semantic evidence</CardTitle>
            <CardDescription>Domain scores, evidence rows, and glossary terms generated from the semantic package.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-md border border-border bg-muted/20 p-3">
              <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Domain scores</div>
              <div className="space-y-2">
                {Object.keys(domainScores).length ? Object.entries(domainScores).map(([name, value]) => (
                  <div key={name}>
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-foreground capitalize">{name.replaceAll("_", " ")}</span>
                      <span className="tabular-nums text-muted-foreground">{Math.round((value ?? 0) * 100)}%</span>
                    </div>
                    <div className="mt-1 h-2 overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full bg-primary" style={{ width: `${Math.round((value ?? 0) * 100)}%` }} />
                    </div>
                  </div>
                )) : <div className="text-xs text-muted-foreground">No semantic domain scores available yet.</div>}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <TraceLink traceId={data?.trace_id} label="Open trace" />
              </div>
            </div>

            <div>
              <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Evidence</div>
              <div className="space-y-2">
                {evidenceRows.length ? evidenceRows.map((item) => (
                  <div key={item.id} className="rounded-md border border-border bg-background p-3">
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-medium">{item.evidence_type}</div>
                      <Badge variant="outline" className="text-[10px] uppercase">{item.evidence_source}</Badge>
                    </div>
                    <pre className="mt-2 overflow-auto rounded bg-muted/30 p-2 text-[11px] leading-5 text-muted-foreground">
                      {JSON.stringify(item.evidence_json, null, 2)}
                    </pre>
                  </div>
                )) : <div className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">No persisted semantic evidence yet.</div>}
              </div>
            </div>

            <div>
              <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Glossary</div>
              <div className="relative pb-2">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search terms…" className="h-8 pl-9 text-sm" />
              </div>
              <Accordion type="single" collapsible className="w-full">
                {filteredGlossary.length ? filteredGlossary.map((g) => (
                  <AccordionItem key={g.term} value={g.term}>
                    <AccordionTrigger className="text-sm hover:no-underline">
                      <span className="flex items-center gap-2">
                        <BookOpenText className="h-3.5 w-3.5 text-primary" />
                        {g.term}
                      </span>
                    </AccordionTrigger>
                    <AccordionContent className="text-xs text-muted-foreground">{g.definition}</AccordionContent>
                  </AccordionItem>
                )) : <div className="text-sm text-muted-foreground">No glossary terms found yet.</div>}
              </Accordion>
            </div>
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Semantic traceability</CardTitle>
          <CardDescription>Evidence rows, domain scores, and package confidence for the selected database.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <MetricCard label="Confidence" value={`${Math.round((evidence?.confidence_score ?? data?.confidence_score ?? 0) * 100)}%`} icon={Activity} tone="info" />
              <MetricCard label="Entities" value={String(entities.length)} icon={Sparkles} tone="success" />
              <MetricCard label="Processes" value={String(processes.length)} icon={Workflow} tone="default" />
            </div>
            <div className="space-y-2">
              <div className="text-xs uppercase tracking-wider text-muted-foreground">Evidence payload</div>
              <pre className="max-h-64 overflow-auto rounded-md border border-border bg-muted/20 p-3 text-[11px] leading-5 text-muted-foreground">
                {JSON.stringify(evidenceRows ?? [], null, 2)}
              </pre>
            </div>
          </div>
          <div className="space-y-2">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Glossary trace</div>
            <div className="space-y-2">
              {filteredGlossary.slice(0, 5).length ? (
                filteredGlossary.slice(0, 5).map((item) => (
                  <div key={item.term} className="rounded-md border border-border bg-card p-3">
                    <div className="text-sm font-medium">{item.term}</div>
                    <div className="mt-1 text-xs text-muted-foreground">{item.definition}</div>
                  </div>
                ))
              ) : (
                <div className="text-sm text-muted-foreground">No glossary trace available yet.</div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
