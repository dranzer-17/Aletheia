"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { 
  LayoutDashboard, 
  MessageSquare, // Chatbot
  TrendingUp,    // Trends
  Globe,         // 3D Globe
  ShieldAlert,   // Misinformation
  Share2,        // Social Network Graph
  Scan,          // AI Detection
  LogOut, 
  ShieldCheck,
  Video          // Deepfake Detection
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ConfirmDialog } from "@/components/ConfirmDialog";

const menuItems = [
  { name: "Overview", href: "/dashboard", icon: LayoutDashboard },
  { name: "AI Chatbot", href: "/dashboard/chatbot", icon: MessageSquare },
  { name: "Live Trends", href: "/dashboard/trends", icon: TrendingUp },
  { name: "3D Globe", href: "/dashboard/globe", icon: Globe },
  { name: "Fake Detection", href: "/dashboard/detection", icon: ShieldAlert },
  { name: "AI Detection", href: "/dashboard/ai-detection", icon: Scan },
  { name: "Deepfake Detection", href: "/dashboard/deepfake", icon: Video },
  { name: "Social Network Graph", href: "/dashboard/social-graph", icon: Share2 },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [showLogoutDialog, setShowLogoutDialog] = useState(false);
  const [indicatorStyle, setIndicatorStyle] = useState({ top: 0, height: 0 });
  const navRef = useRef<HTMLElement>(null);
  const itemRefs = useRef<(HTMLAnchorElement | null)[]>([]);

  // Calculate active item index and position
  useEffect(() => {
    const activeIndex = menuItems.findIndex(item => pathname === item.href);
    if (activeIndex !== -1 && itemRefs.current[activeIndex]) {
      const activeItem = itemRefs.current[activeIndex];
      const nav = navRef.current;
      if (activeItem && nav) {
        // Use requestAnimationFrame to ensure DOM is fully rendered
        requestAnimationFrame(() => {
          const navRect = nav.getBoundingClientRect();
          const itemRect = activeItem.getBoundingClientRect();
          // Calculate position relative to nav container
          const topOffset = itemRect.top - navRect.top;
          setIndicatorStyle({
            top: topOffset,
            height: itemRect.height,
          });
        });
      }
    }
  }, [pathname]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    router.push("/auth/login");
  };

  return (
    <>
      <aside className="w-72 h-screen bg-[var(--glass-bg)] backdrop-blur-xl border-r border-[var(--glass-border)] flex flex-col fixed left-0 top-0 z-40 transition-all duration-300 ease-in-out">
        
        {/* LOGO */}
        <Link href="/" className="h-20 flex items-center px-6 border-b border-[var(--glass-border)]">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-foreground rounded-lg">
              <ShieldCheck className="w-5 h-5 text-background" />
            </div>
            <span className="font-semibold text-lg tracking-tight text-foreground">ALETHEIA</span>
          </div>
        </Link>

        {/* NAV */}
        <nav ref={navRef} className="flex-1 py-6 flex flex-col gap-1.5 px-4 relative">
          {/* Sliding Glass Indicator */}
          <div
            className="absolute left-4 right-4 rounded-lg bg-foreground/10 backdrop-blur-sm border border-foreground/20 transition-all duration-500 ease-in-out pointer-events-none"
            style={{
              top: `${indicatorStyle.top}px`,
              height: `${indicatorStyle.height}px`,
            }}
          />
          
          {menuItems.map((item, index) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                ref={(el) => { itemRefs.current[index] = el; }}
                className={cn(
                  "group flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium relative z-10",
                  "transition-all duration-300 ease-in-out",
                  isActive 
                    ? "text-foreground" 
                    : "text-foreground/70 hover:text-foreground"
                )}
              >
                {/* Hover glass effect */}
                {!isActive && (
                  <div className="absolute inset-0 rounded-lg bg-foreground/5 backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-opacity duration-300 ease-in-out pointer-events-none" />
                )}
                
                <item.icon className={cn(
                  "w-5 h-5 shrink-0 relative z-10 transition-all duration-300 ease-in-out",
                  isActive 
                    ? "text-foreground" 
                    : "text-foreground/50 group-hover:text-foreground"
                )} />
                <span className="relative z-10 transition-all duration-300 ease-in-out">{item.name}</span>
              </Link>
            );
          })}
        </nav>

        {/* LOGOUT */}
        <div className="p-4 border-t border-[var(--glass-border)]">
          <button 
            onClick={() => setShowLogoutDialog(true)}
            className="flex items-center gap-3 w-full px-4 py-3 text-sm font-medium text-red-500 hover:bg-red-500/10 rounded-lg transition-all duration-300 ease-in-out transform hover:scale-[1.02] active:scale-[0.98]"
          >
            <LogOut className="w-5 h-5 shrink-0" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Logout Confirmation Dialog */}
      <ConfirmDialog
        open={showLogoutDialog}
        onOpenChange={setShowLogoutDialog}
        onConfirm={handleLogout}
        title="Sign Out"
        description="Are you sure you want to sign out? You will need to log in again to access your account."
        confirmText="Sign Out"
        cancelText="Cancel"
      />
    </>
  );
}