"use client";

import { Sidebar } from "@/components/Sidebar";
import { ModeToggle } from "@/components/ModeToggle";
import { ProfileDropdown } from "@/components/ProfileDropdown";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background flex">
      
      {/* 1. FIXED SIDEBAR */}
      <Sidebar />

      {/* 2. MAIN CONTENT AREA (Pushed right by 72px/18rem) */}
      <main className="flex-1 ml-72 flex flex-col">
        
        {/* TOP HEADER */}
        <header className="h-16 border-b border-[var(--glass-border)] flex items-center justify-between px-8 bg-[var(--glass-bg)] backdrop-blur-xl sticky top-0 z-30">
          <h2 className="font-medium text-foreground/90 text-sm tracking-tight">Dashboard</h2>
          <div className="flex items-center gap-3">
            <ModeToggle />
            <ProfileDropdown />
          </div>
        </header>

        {/* PAGE CONTENT */}
        <div className="p-8 overflow-y-auto h-[calc(100vh-4rem)]">
          {children}
        </div>
      </main>
    </div>
  );
}