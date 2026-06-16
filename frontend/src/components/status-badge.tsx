import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  Loader2,
  PauseCircle,
  HelpCircle,
  Archive,
  type LucideIcon,
} from "lucide-react";

export type StatusKind =
  | "success"
  | "running"
  | "queued"
  | "warning"
  | "failed"
  | "paused"
  | "neutral"
  | "active"
  | "disconnected"
  | "archived"
  | "deleted"
  | "unknown";

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
    label: "Neutral",
    icon: Clock,
    cls: "bg-muted text-muted-foreground border-border",
  },
  active: {
    label: "Active",
    icon: CheckCircle2,
    cls: "bg-[var(--success)]/10 text-[var(--success)] border-[var(--success)]/25",
  },
  disconnected: {
    label: "Disconnected",
    icon: PauseCircle,
    cls: "bg-muted text-muted-foreground border-border",
  },
  archived: {
    label: "Archived",
    icon: Archive,
    cls: "bg-[var(--warning)]/15 text-[var(--warning)] border-[var(--warning)]/30",
  },
  deleted: {
    label: "Deleted",
    icon: XCircle,
    cls: "bg-destructive/10 text-destructive border-destructive/25",
  },
  unknown: {
    label: "Unknown",
    icon: HelpCircle,
    cls: "bg-muted text-muted-foreground border-border",
  },
};

function normalizeStatus(status?: string | null): StatusKind {
  const value = (status ?? "unknown").trim().toLowerCase();
  if (value in config) return value as StatusKind;
  if (value === "completed" || value === "complete" || value === "done") return "success";
  if (value === "success") return "success";
  if (value === "running" || value === "in_progress" || value === "in-progress" || value === "processing")
    return "running";
  if (value === "queued" || value === "pending") return "queued";
  if (value === "failed" || value === "error" || value === "failure") return "failed";
  if (value === "cancelled" || value === "canceled" || value === "partial") return "warning";
  if (value === "paused" || value === "stopped") return "paused";
  if (value === "active") return "active";
  if (value === "disconnected") return "disconnected";
  if (value === "archived") return "archived";
  if (value === "deleted") return "deleted";
  return "unknown";
}

export function StatusBadge({
  status,
  label,
  className,
}: {
  status?: string | null;
  label?: string;
  className?: string;
}) {
  const normalized = normalizeStatus(status);
  const c = config[normalized] ?? config.unknown;
  const Icon = c.icon;
  return (
    <Badge
      variant="outline"
      className={cn("gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium", c.cls, className)}
    >
      <Icon className={cn("h-3 w-3", normalized === "running" && "animate-spin")} />
      {label ?? c.label}
    </Badge>
  );
}
