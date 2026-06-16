import { useEffect, useRef, type ReactNode } from "react";
import { useLocation } from "@tanstack/react-router";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "./app-sidebar";
import { AppHeader } from "./app-header";
import { DatabaseContextBar } from "@/components/common/DatabaseContextBar";
import { DatabaseProvider } from "@/context/database-context";

export function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation();
  const mainRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0, behavior: "auto" });
  }, [location.pathname]);

  return (
    <DatabaseProvider>
      <SidebarProvider
        style={
          {
            "--sidebar-width": "17rem",
            "--sidebar-width-icon": "3.5rem",
          } as React.CSSProperties
        }
        className="h-screen items-stretch overflow-hidden"
      >
        <AppSidebar />
        <SidebarInset className="relative z-0 flex h-screen min-w-0 flex-1 flex-col overflow-hidden bg-background">
          <AppHeader />
          <DatabaseContextBar />
          <main ref={mainRef} className="relative z-0 flex-1 overflow-y-auto overflow-x-hidden">
            <div className="mx-auto w-full max-w-[1600px] px-4 py-5 sm:px-6 lg:px-8">{children}</div>
          </main>
        </SidebarInset>
      </SidebarProvider>
    </DatabaseProvider>
  );
}
