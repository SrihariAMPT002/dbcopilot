import type { LucideIcon } from "lucide-react";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

export function MetricCard({
  label,
  value,
  hint,
  icon: Icon,
  trend,
  progress,
  tone = "default",
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon?: LucideIcon;
  trend?: { value: string; positive?: boolean };
  progress?: number;
  tone?: "default" | "success" | "warning" | "danger" | "info";
}) {
  const toneRing: Record<string, string> = {
    default: "from-primary/15 to-primary/0 text-primary",
    success: "from-[var(--success)]/15 to-[var(--success)]/0 text-[var(--success)]",
    warning: "from-[var(--warning)]/20 to-[var(--warning)]/0 text-[var(--warning)]",
    danger: "from-destructive/15 to-destructive/0 text-destructive",
    info: "from-[var(--info)]/15 to-[var(--info)]/0 text-[var(--info)]",
  };
  return (
    <Card className="relative overflow-hidden border-border bg-card p-4 transition-shadow hover:shadow-[var(--shadow-md)]">
      <div
        className={cn(
          "pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-gradient-to-br opacity-60 blur-2xl",
          toneRing[tone],
        )}
      />
      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </div>
          <div className="mt-1.5 flex items-baseline gap-2">
            <div className="text-2xl font-semibold tracking-tight text-foreground">{value}</div>
            {trend && (
              <span
                className={cn(
                  "inline-flex items-center gap-0.5 text-xs font-medium",
                  trend.positive ? "text-[var(--success)]" : "text-destructive",
                )}
              >
                {trend.positive ? (
                  <ArrowUpRight className="h-3 w-3" />
                ) : (
                  <ArrowDownRight className="h-3 w-3" />
                )}
                {trend.value}
              </span>
            )}
          </div>
          {hint && <div className="mt-1 truncate text-xs text-muted-foreground">{hint}</div>}
        </div>
        {Icon && (
          <div
            className={cn(
              "grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-gradient-to-br",
              toneRing[tone],
            )}
          >
            <Icon className="h-4 w-4" />
          </div>
        )}
      </div>
      {typeof progress === "number" && (
        <div className="relative mt-3">
          <Progress value={progress} className="h-1.5" />
        </div>
      )}
    </Card>
  );
}