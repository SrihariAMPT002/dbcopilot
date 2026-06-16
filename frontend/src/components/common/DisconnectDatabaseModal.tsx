import { useEffect, useState } from "react";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  connectionName: string;
  onConfirm: (confirmationText: string) => void | Promise<void>;
  busy?: boolean;
};

export function DisconnectDatabaseModal({ open, onOpenChange, connectionName, onConfirm, busy }: Props) {
  const [value, setValue] = useState("");
  const exactMatch = value.trim() === connectionName;

  useEffect(() => {
    if (!open) setValue("");
  }, [open, connectionName]);

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Disconnect database</AlertDialogTitle>
          <AlertDialogDescription>
            Disconnecting this database stops sync jobs, AI pipelines, embedding refresh, and scheduled tasks while
            preserving metadata, governance, semantics, relationships, KPI, Prompt Studio, embeddings, readiness, and
            observability.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-2">
          <div className="text-sm font-medium">Type the connection name to continue</div>
          <Input value={value} onChange={(event) => setValue(event.target.value)} placeholder={connectionName} />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={() => setValue("")}>Cancel</AlertDialogCancel>
          <AlertDialogAction disabled={!exactMatch || busy} onClick={() => onConfirm(value.trim())}>
            Disconnect
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
