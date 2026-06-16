import { Card, CardContent } from "@/components/ui/card";
import { CoverageBar } from "@/components/coverage-bar";

export function DimensionScoreCard({
  label,
  score,
  confidence,
}: {
  label: string;
  score: number;
  confidence?: number | null;
}) {
  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex items-center justify-between gap-2">
          <div className="text-sm font-medium text-foreground">{label}</div>
          <div className="text-sm text-muted-foreground">{Math.round((confidence ?? 0) * 100)}%</div>
        </div>
        <CoverageBar value={score} />
      </CardContent>
    </Card>
  );
}
