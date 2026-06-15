import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  Loader2,
  PauseCircle,
  type LucideIcon,
} from "lucide-react";

export type StatusKind =
  | "success"
  | "running"
  | "queued"
  | "warning"
  | "failed"
  | "paused"
  | "neutral";

const config: Record<StatusKind, { label: string; icon: LucideIcon; cls: string }> = {
  success: {
    label: "Completed",
    icon: CheckCircle2,
    cls: "bg-[var(--success)]/10 text-[var(--success)] border-[var(--success)]/25",
  },
  running: {
    label: "Running",
    icon: Loader2,
    cls: "bg-[var(--info)]/10 text-[var(--info)] border-[var(--info)]/25",
  },
  queued: {
    label: "Queued",
    icon: Clock,
    cls: "bg-muted text-muted-foreground border-border",
  },
  warning: {
    label: "Warning",
    icon: AlertTriangle,
    cls: "bg-[var(--warning)]/15 text-[var(--warning)] border-[var(--warning)]/30",
  },
  failed: {
    label: "Failed",
    icon: XCircle,
    cls: "bg-destructive/10 text-destructive border-destructive/25",
  },
  paused: {
    label: "Paused",
    icon: PauseCircle,
    cls: "bg-muted text-muted-foreground border-border",
  },
  neutral: {
    label: "—",
    icon: Clock,
    cls: "bg-muted text-muted-foreground border-border",
  },
};

export function StatusBadge({
  status,
  label,
  className,
}: {
  status: StatusKind;
  label?: string;
  className?: string;
}) {
  const c = config[status];
  const Icon = c.icon;
  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        c.cls,
        className,
      )}
    >
      <Icon className={cn("h-3 w-3", status === "running" && "animate-spin")} />
      {label ?? c.label}
    </Badge>
  );
}