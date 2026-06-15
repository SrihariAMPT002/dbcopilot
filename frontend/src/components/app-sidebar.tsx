import { Link, useRouterState } from "@tanstack/react-router";
import { Database, ChevronsLeft } from "lucide-react";

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarFooter,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import { Badge } from "@/components/ui/badge";
import { navGroups } from "@/lib/nav";
import { cn } from "@/lib/utils";

export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const pathname = useRouterState({ select: (r) => r.location.pathname });

  const isActive = (path: string) =>
    path === "/" ? pathname === "/" : pathname === path || pathname.startsWith(path + "/");

  return (
    <Sidebar collapsible="icon" className="border-r border-sidebar-border">
      <SidebarHeader className="border-b border-sidebar-border">
        <div className={cn("flex items-center gap-2 px-2 py-1.5", collapsed && "justify-center px-0")}>
          <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-primary to-primary-glow text-primary-foreground shadow-[var(--shadow-glow)]">
            <Database className="h-4 w-4" />
          </div>
          {!collapsed && (
            <div className="flex min-w-0 flex-col leading-tight">
              <span className="truncate text-sm font-semibold text-sidebar-foreground">DBCopilot</span>
              <span className="truncate text-[10px] uppercase tracking-wider text-sidebar-foreground/60">
                Database Intelligence
              </span>
            </div>
          )}
        </div>
      </SidebarHeader>

      <SidebarContent className="gap-0">
        {navGroups.map((group) => (
          <SidebarGroup key={group.label}>
            {!collapsed && (
              <SidebarGroupLabel className="text-[10px] uppercase tracking-wider text-sidebar-foreground/50">
                {group.label}
              </SidebarGroupLabel>
            )}
            <SidebarGroupContent>
              <SidebarMenu>
                {group.items.map((item) => {
                  const active = isActive(item.to);
                  return (
                    <SidebarMenuItem key={item.to}>
                      <SidebarMenuButton
                        asChild
                        isActive={active}
                        tooltip={item.title}
                        className={cn(
                          "data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-primary data-[active=true]:font-medium",
                          "data-[active=true]:before:absolute data-[active=true]:before:left-0 data-[active=true]:before:top-1.5 data-[active=true]:before:h-[calc(100%-12px)] data-[active=true]:before:w-[2px] data-[active=true]:before:rounded-full data-[active=true]:before:bg-sidebar-primary",
                          "relative",
                        )}
                      >
                        <Link to={item.to}>
                          <item.icon className="h-4 w-4 shrink-0" />
                          <span className="truncate">{item.title}</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border">
        {!collapsed ? (
          <div className="flex flex-col gap-2 px-2 py-2">
            <div className="flex items-center justify-between gap-2 rounded-md bg-sidebar-accent/60 px-2 py-1.5">
              <div className="flex min-w-0 items-center gap-2">
                <span className="h-2 w-2 shrink-0 rounded-full bg-[var(--success)] shadow-[0_0_8px_var(--success)]" />
                <span className="truncate text-xs text-sidebar-foreground/80">Backend online</span>
              </div>
              <Badge variant="outline" className="border-sidebar-border text-[10px] text-sidebar-foreground/70">
                v1.4.2
              </Badge>
            </div>
            <SidebarTrigger className="self-end text-sidebar-foreground/60 hover:text-sidebar-foreground">
              <ChevronsLeft className="h-4 w-4" />
            </SidebarTrigger>
          </div>
        ) : (
          <SidebarTrigger className="mx-auto text-sidebar-foreground/60" />
        )}
      </SidebarFooter>
    </Sidebar>
  );
}