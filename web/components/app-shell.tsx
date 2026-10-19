"use client";

import {
  BellRingingIcon,
  ChartLineIcon,
  GlobeHemisphereWestIcon,
  ListIcon,
  MoonIcon,
  SignOutIcon,
  SlidersHorizontalIcon,
  SunIcon,
  PlanetIcon,
} from "@phosphor-icons/react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { Wordmark } from "@/components/brand";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { api, ApiError, type User } from "@/lib/api";
import { cn } from "@/lib/utils";

type Role = User["role"];

const NAV: { href: string; label: string; icon: typeof BellRingingIcon; roles?: Role[] }[] = [
  { href: "/dashboard", label: "Alerts", icon: BellRingingIcon },
  { href: "/globe", label: "Globe", icon: GlobeHemisphereWestIcon },
  { href: "/satellites", label: "Satellites", icon: PlanetIcon },
  { href: "/evaluation", label: "Evaluation", icon: ChartLineIcon, roles: ["Evaluator", "Administrator"] },
  { href: "/admin", label: "Administration", icon: SlidersHorizontalIcon, roles: ["Administrator"] },
];

const UserContext = createContext<User | null>(null);

/** The signed-in user, once the shell has loaded it (null while loading). */
export function useShellUser() {
  return useContext(UserContext);
}

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const dark = mounted && resolvedTheme === "dark";
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      onClick={() => setTheme(dark ? "light" : "dark")}
    >
      {dark ? <SunIcon /> : <MoonIcon />}
    </Button>
  );
}

function NavLinks({ user, onNavigate }: { user: User | null; onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex flex-col gap-0.5">
      {NAV.filter((item) => !item.roles || (user && item.roles.includes(user.role))).map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[14px] text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-foreground",
              active && "bg-sidebar-accent font-medium text-sidebar-foreground",
            )}
          >
            <Icon className="size-4" weight={active ? "fill" : "regular"} />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

function SidebarFooter({ user, onLogout }: { user: User | null; onLogout: () => void }) {
  return (
    <div className="mt-auto flex flex-col gap-3 border-t border-sidebar-border pt-3">
      <p className="text-[12px] leading-relaxed text-muted-foreground">
        Telemetry is replayed from the NASA SMAP/MSL dataset. Orbits are propagated live from public TLEs.
      </p>
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-medium" id="currentUserName">
            {user ? `${user.firstName} ${user.lastName}` : " "}
          </p>
          <p className="truncate text-[12px] text-muted-foreground" id="currentUserRole">
            {user?.role ?? " "}
          </p>
        </div>
        <ThemeToggle />
        <Button id="logoutBtn" variant="ghost" size="icon-sm" aria-label="Sign out" title="Sign out" onClick={onLogout}>
          <SignOutIcon />
        </Button>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) router.replace("/login");
      });
  }, [router]);

  async function logout() {
    await fetch("/api/logout", { method: "POST" });
    router.replace("/login");
  }

  return (
    <UserContext.Provider value={user}>
      <div className="flex min-h-dvh">
        <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col gap-6 border-r border-sidebar-border bg-sidebar px-3 py-4 md:flex">
          <Link href="/dashboard" className="px-2.5">
            <Wordmark />
          </Link>
          <NavLinks user={user} />
          <SidebarFooter user={user} onLogout={logout} />
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          {/* Narrow screens: a top bar with the navigation in a sheet. */}
          <div className="sticky top-0 z-30 flex h-12 items-center justify-between border-b bg-sidebar px-4 md:hidden">
            <Link href="/dashboard">
              <Wordmark />
            </Link>
            <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon-sm" aria-label="Open menu">
                  <ListIcon />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="flex w-64 flex-col gap-6 bg-sidebar p-4">
                <SheetTitle className="px-2.5">
                  <Wordmark />
                </SheetTitle>
                <NavLinks user={user} onNavigate={() => setMenuOpen(false)} />
                <SidebarFooter user={user} onLogout={logout} />
              </SheetContent>
            </Sheet>
          </div>
          <main className="min-w-0 flex-1">{children}</main>
        </div>
      </div>
    </UserContext.Provider>
  );
}
