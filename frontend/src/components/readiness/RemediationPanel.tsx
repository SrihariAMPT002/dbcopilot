import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { Lightbulb } from "lucide-react";

export function RemediationPanel({
  remediations,
}: {
  remediations: Array<{ issue: string; recommendation: string; priority?: string | null; confidence_score: number }>;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Remediation</CardTitle>
        <CardDescription>AI-generated actions to improve readiness.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {remediations.length ? (
          remediations.map((item) => (
            <div key={`${item.issue}-${item.recommendation}`} className="rounded-md border border-border bg-card p-3">
              <div className="text-sm font-medium text-foreground">{item.issue}</div>
              <div className="mt-1 text-sm text-muted-foreground">{item.recommendation}</div>
            </div>
          ))
        ) : (
          <EmptyState icon={Lightbulb} title="No remediation yet" description="Generate readiness to surface AI recommendations." />
        )}
      </CardContent>
    </Card>
  );
}
