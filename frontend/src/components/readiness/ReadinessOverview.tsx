import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function ReadinessOverview({
  overallScore,
  maturityLevel,
  confidence,
  traceId,
}: {
  overallScore: number;
  maturityLevel: string;
  confidence?: number | null;
  traceId?: string | null;
}) {
  return (
    <Card>
      <CardContent className="flex flex-wrap items-center justify-between gap-4 p-4">
        <div>
          <div className="text-sm text-muted-foreground">Overall AI readiness</div>
          <div className="text-3xl font-semibold text-foreground">{overallScore}</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">{maturityLevel}</Badge>
          <Badge variant="outline">{Math.round((confidence ?? 0) * 100)}% confidence</Badge>
          <Badge variant="outline">{traceId ?? "no trace"}</Badge>
        </div>
      </CardContent>
    </Card>
  );
}
