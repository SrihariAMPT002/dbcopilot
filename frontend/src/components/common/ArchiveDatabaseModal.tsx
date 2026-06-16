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

export function ArchiveDatabaseModal({ open, onOpenChange, connectionName, onConfirm, busy }: Props) {
  const [value, setValue] = useState("");
  const exactMatch = value.trim() === connectionName;

  useEffect(() => {
    if (!open) setValue("");
  }, [open, connectionName]);

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Archive database</AlertDialogTitle>
          <AlertDialogDescription>
            Archiving freezes execution and hides the database from default lists while preserving all intelligence
            artifacts for later restoration.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-2">
          <div className="text-sm font-medium">Type the connection name to continue</div>
          <Input value={value} onChange={(event) => setValue(event.target.value)} placeholder={connectionName} />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={() => setValue("")}>Cancel</AlertDialogCancel>
          <AlertDialogAction disabled={!exactMatch || busy} onClick={() => onConfirm(value.trim())}>
            Archive
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
