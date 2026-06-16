import { useRouterState } from "@tanstack/react-router";
import { Link } from "@tanstack/react-router";
import { Search, Command as CmdIcon, Sun, Moon, ChevronDown } from "lucide-react";
import { useEffect, useState } from "react";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Breadcrumbs } from "@/components/common/Breadcrumbs";
import { navGroups } from "@/lib/nav";

export function AppHeader() {
  const pathname = useRouterState({ select: (r) => r.location.pathname });
  const current = navGroups.flatMap((g) => g.items).find((i) =>
    i.to === "/" ? pathname === "/" : pathname === i.to || pathname.startsWith(i.to + "/"),
  );
  const title = current?.title ?? "DBCopilot";

  const [theme, setTheme] = useState<"light" | "dark">("light");
  useEffect(() => {
    const stored = localStorage.getItem("dbcopilot-theme") as "light" | "dark" | null;
    const initial = stored ?? "light";
    setTheme(initial);
    document.documentElement.classList.toggle("dark", initial === "dark");
  }, []);
  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.classList.toggle("dark", next === "dark");
    localStorage.setItem("dbcopilot-theme", next);
  };

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 border-b border-border bg-background/90 px-4 backdrop-blur-md sm:px-5">
      <SidebarTrigger className="md:hidden" />

      <div className="hidden min-w-0 flex-1 items-center gap-3 md:flex">
        <Breadcrumbs />
      </div>
      <h1 className="truncate text-sm font-semibold text-foreground md:hidden">{title}</h1>

      <div className="relative hidden flex-1 max-w-md lg:flex">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search tables, columns, KPIs, prompts…"
          className="h-9 border-border bg-muted/40 pl-9 pr-14 text-sm focus-visible:bg-background"
        />
        <kbd className="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 items-center gap-1 rounded border border-border bg-background px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground sm:inline-flex">
          <CmdIcon className="h-3 w-3" /> K
        </kbd>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <Separator orientation="vertical" className="hidden h-6 sm:block" />
        <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label="Toggle theme">
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
        <Separator orientation="vertical" className="hidden h-6 sm:block" />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="h-9 gap-2 px-1.5 sm:px-2">
              <Avatar className="h-7 w-7">
                <AvatarFallback className="bg-gradient-to-br from-primary to-primary-glow text-[11px] font-semibold text-primary-foreground">
                  DB
                </AvatarFallback>
              </Avatar>
              <div className="hidden text-left leading-tight sm:block">
                <div className="text-xs font-medium text-foreground">Data Platform</div>
                <div className="text-[10px] text-muted-foreground">admin</div>
              </div>
              <ChevronDown className="hidden h-3.5 w-3.5 text-muted-foreground sm:block" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>Workspace</DropdownMenuLabel>
            <DropdownMenuItem asChild>
              <Link to="/settings">Members</Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link to="/settings">API tokens</Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link to="/jobs">Audit log</Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled>Sign out</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
