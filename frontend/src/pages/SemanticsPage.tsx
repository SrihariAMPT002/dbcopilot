import { useMemo, useState } from "react";
import { Activity, BookOpenText, Building2, Search, Sparkles, Workflow } from "lucide-react";
import { useDatabaseContext } from "@/context/database-context";
import { useSemantics, useSemanticEvidence } from "@/hooks/useSemantics";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { TraceLink } from "@/components/common/TraceLink";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";

export function SemanticsPage() {
  const { selectedDatabase } = useDatabaseContext();
  const dbId = selectedDatabase?.database_id ?? null;
  const { data } = useSemantics(dbId);
  const { data: evidence } = useSemanticEvidence(dbId);
  const [search, setSearch] = useState("");

  const entities = data?.business_entities ?? [];
  const processes = data?.business_processes ?? [];
  const capabilities = data?.business_capabilities ?? [];
  const glossary = data?.business_glossary ?? [];
  const filteredGlossary = useMemo(
    () => glossary.filter((item) => `${item.term} ${item.definition}`.toLowerCase().includes(search.toLowerCase())),
    [glossary, search],
  );
  const evidenceChips = (evidence?.evidence ?? [])
    .flatMap((item) => [item.evidence_type, item.evidence_source])
    .filter(Boolean)
    .slice(0, 12);

  const domainScores = evidence?.domain_scores ?? data?.domain_scores ?? {};
  const confidence = Math.round((evidence?.confidence_score ?? data?.confidence_score ?? 0) * 100);

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Intelligence" title="Semantics" description="Business domain, entities, processes, capabilities, glossary, and semantic evidence from persisted semantic packages." />
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Confidence" value={`${confidence}%`} icon={Activity} tone="info" />
        <MetricCard label="Entities" value={String(entities.length)} icon={Sparkles} tone="success" />
        <MetricCard label="Processes" value={String(processes.length)} icon={Workflow} tone="default" />
        <MetricCard label="Glossary terms" value={String(glossary.length)} icon={BookOpenText} tone="warning" />
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
                <Building2 className="mr-1 h-3 w-3" /> Domain
              </Badge>
              <Badge variant="outline" className="text-[11px]">{data?.business_domain ?? evidence?.business_domain ?? "Pending discovery"}</Badge>
              <Badge variant="outline" className="text-[11px]">{confidence}%</Badge>
            </div>
            <CardTitle className="text-base">Business summary</CardTitle>
            <CardDescription>{data?.semantic_summary ?? "No semantic summary available yet for this database."}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
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
              <div className="grid gap-2 md:grid-cols-2">
                {processes.length ? processes.map((p) => (
                  <div key={p} className="rounded-md border border-border bg-card p-3 text-sm text-foreground">{p}</div>
                )) : <div className="text-sm text-muted-foreground">No semantic processes found yet.</div>}
              </div>
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
            <CardDescription>Domain scores, evidence chips, and glossary terms from the semantic package.</CardDescription>
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
              <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Evidence chips</div>
              <div className="flex flex-wrap gap-2">
                {evidenceChips.length ? evidenceChips.map((chip) => (
                  <Badge key={chip} variant="outline" className="text-[10px] uppercase">{chip}</Badge>
                )) : <div className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">No persisted semantic evidence yet.</div>}
              </div>
            </div>
            <div>
              <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Glossary</div>
              <div className="relative pb-2">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search terms..." className="h-8 pl-9 text-sm" />
              </div>
              <Accordion type="single" collapsible className="w-full">
                {filteredGlossary.length ? filteredGlossary.map((g) => (
                  <AccordionItem key={g.term} value={g.term}>
                    <AccordionTrigger className="text-sm hover:no-underline">
                      <span className="flex items-center gap-2"><BookOpenText className="h-3.5 w-3.5 text-primary" />{g.term}</span>
                    </AccordionTrigger>
                    <AccordionContent className="text-xs text-muted-foreground">{g.definition}</AccordionContent>
                  </AccordionItem>
                )) : <div className="text-sm text-muted-foreground">No glossary terms found yet.</div>}
              </Accordion>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
