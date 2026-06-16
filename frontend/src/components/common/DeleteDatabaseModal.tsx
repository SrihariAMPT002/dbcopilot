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

export function DeleteDatabaseModal({ open, onOpenChange, connectionName, onConfirm, busy }: Props) {
  const [value, setValue] = useState("");
  const exactMatch = value.trim() === connectionName || value.trim() === `DELETE ${connectionName}`;

  useEffect(() => {
    if (!open) setValue("");
  }, [open, connectionName]);

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete database</AlertDialogTitle>
          <AlertDialogDescription>
            Permanent deletion removes metadata, packages, embeddings, prompt artifacts, readiness snapshots, jobs,
            and traces if selected. This action cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-2">
          <div className="text-sm font-medium">Type the connection name or DELETE {connectionName} to continue</div>
          <Input value={value} onChange={(event) => setValue(event.target.value)} placeholder={connectionName} />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={() => setValue("")}>Cancel</AlertDialogCancel>
          <AlertDialogAction disabled={!exactMatch || busy} onClick={() => onConfirm(value.trim())}>
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
