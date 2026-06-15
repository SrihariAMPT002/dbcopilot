import { cn } from "@/lib/utils";

export function CoverageBar({
  value,
  label,
  tone = "primary",
  className,
}: {
  value: number;
  label?: string;
  tone?: "primary" | "success" | "warning" | "danger";
  className?: string;
}) {
  const toneCls: Record<string, string> = {
    primary: "bg-gradient-to-r from-primary to-primary-glow",
    success: "bg-[var(--success)]",
    warning: "bg-[var(--warning)]",
    danger: "bg-destructive",
  };
  const safe = Math.max(0, Math.min(100, value));
  return (
    <div className={cn("space-y-1", className)}>
      {label && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">{label}</span>
          <span className="font-medium tabular-nums text-foreground">{safe}%</span>
        </div>
      )}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full transition-all", toneCls[tone])} style={{ width: `${safe}%` }} />
      </div>
    </div>
  );
}