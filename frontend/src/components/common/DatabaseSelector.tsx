import { useMemo, useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useDatabaseContext } from "@/context/database-context";

export function DatabaseSelector() {
  const [open, setOpen] = useState(false);
  const { databases, selectedDatabaseId, setSelectedDatabaseId } = useDatabaseContext();
  const selected = useMemo(() => databases.find((db) => db.database_id === selectedDatabaseId), [databases, selectedDatabaseId]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" className="h-9 min-w-[220px] justify-between gap-2">
          <span className="truncate text-left">{selected ? `${selected.database_name} (#${selected.database_id})` : "Select database"}</span>
          <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[320px] p-0" align="end">
        <Command>
          <CommandInput placeholder="Search databases" />
          <CommandList>
            <CommandEmpty>No databases found.</CommandEmpty>
            <CommandGroup heading="Databases">
              {databases.map((db) => (
                <CommandItem
                  key={db.database_id}
                  value={`${db.database_name} ${db.database_id} ${db.db_type}`}
                  onSelect={() => {
                    setSelectedDatabaseId(db.database_id);
                    setOpen(false);
                  }}
                >
                  <div className="flex min-w-0 flex-1 items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate text-sm">{db.database_name}</div>
                      <div className="text-[11px] text-muted-foreground">
                        #{db.database_id}
                        {db.db_type ? ` · ${db.db_type}` : ""}
                      </div>
                    </div>
                    {selectedDatabaseId === db.database_id ? <Check className="h-4 w-4" /> : null}
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
