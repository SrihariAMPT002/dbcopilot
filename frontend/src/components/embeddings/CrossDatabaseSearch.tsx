import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Search } from "lucide-react";

export function CrossDatabaseSearch() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Cross database search</CardTitle>
        <CardDescription>Search across all indexed knowledge collections.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input placeholder="Search across databases..." className="h-9 pl-9" />
          </div>
          <Button size="sm">Search</Button>
        </div>
      </CardContent>
    </Card>
  );
}
