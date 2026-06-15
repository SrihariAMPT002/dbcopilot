import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Card } from "@/components/ui/card";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <Card className="flex flex-col items-center justify-center gap-3 border-dashed bg-muted/20 px-6 py-14 text-center">
      <div className="grid h-12 w-12 place-items-center rounded-full bg-gradient-to-br from-primary/15 to-primary/0 text-primary">
        <Icon className="h-5 w-5" />
      </div>
      <div className="space-y-1">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        {description && (
          <p className="mx-auto max-w-md text-xs text-muted-foreground">{description}</p>
        )}
      </div>
      {action}
    </Card>
  );
}