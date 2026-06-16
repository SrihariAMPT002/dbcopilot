import { ExternalLink } from "lucide-react";

type TraceLinkProps = {
  traceId?: string | null;
  label?: string;
  className?: string;
};

export function TraceLink({ traceId, label = "Open trace", className = "" }: TraceLinkProps) {
  if (!traceId) return null;

  return (
    <a
      href={`/observability?trace_id=${encodeURIComponent(traceId)}`}
      className={`inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline ${className}`.trim()}
    >
      {label}
      <ExternalLink className="h-3 w-3" />
    </a>
  );
}
