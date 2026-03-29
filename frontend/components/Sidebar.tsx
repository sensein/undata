"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useAuth } from "./AuthProvider";

function UserSection({ collapsed }: { collapsed: boolean }) {
  const { user, isAuthenticated, signIn, signOut } = useAuth();

  if (!isAuthenticated) {
    return (
      <button
        onClick={signIn}
        className="w-full text-left text-sm text-gray-400 hover:text-white transition-colors"
      >
        {collapsed ? "→" : "Sign in"}
      </button>
    );
  }

  return (
    <div className="text-sm">
      {!collapsed && (
        <>
          <div className="text-white font-medium truncate">{user?.name}</div>
          <div className="text-xs text-gray-400">{user?.roles?.[0] ?? "viewer"}</div>
          <button
            onClick={signOut}
            className="mt-2 text-xs text-gray-500 hover:text-white transition-colors"
          >
            Sign out
          </button>
        </>
      )}
      {collapsed && (
        <div className="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center text-white text-xs" title={user?.name}>
          {user?.name?.[0]?.toUpperCase() ?? "?"}
        </div>
      )}
    </div>
  );
}

interface NavItem {
  label: string;
  href: string;
  icon: string;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    title: "BROWSE",
    items: [
      { label: "Elements", href: "/elements", icon: "◆" },
      { label: "Schemas", href: "/schemas", icon: "◇" },
      { label: "Values", href: "/values", icon: "●" },
      { label: "Value Sets", href: "/valuesets", icon: "○" },
      { label: "Transforms", href: "/transforms", icon: "⇄" },
    ],
  },
  {
    title: "CURATION",
    items: [
      { label: "Queue", href: "/curation", icon: "⚑" },
      { label: "Activity", href: "/activity", icon: "◎" },
    ],
  },
  {
    title: "PIPELINE",
    items: [
      { label: "Runs", href: "/runs", icon: "▶" },
    ],
  },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();

  return (
    <>
      {/* Mobile toggle */}
      <button
        className="md:hidden fixed top-3 left-3 z-50 p-2 bg-gray-800 text-white rounded"
        onClick={() => setCollapsed(!collapsed)}
        aria-label="Toggle navigation"
      >
        ☰
      </button>

      {/* Sidebar */}
      <aside
        className={`
          fixed top-0 left-0 h-full bg-gray-900 text-gray-300
          transition-all duration-200 z-40 overflow-y-auto
          ${collapsed ? "w-16" : "w-52"}
          max-md:${collapsed ? "-translate-x-full" : "translate-x-0"}
          md:translate-x-0
        `}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-4 border-b border-gray-700">
          {!collapsed && (
            <Link href="/" className="text-lg font-bold text-white">
              undata
            </Link>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="text-gray-400 hover:text-white hidden md:block"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? "→" : "←"}
          </button>
        </div>

        {/* Nav groups */}
        <nav className="py-4">
          {NAV_GROUPS.map((group) => (
            <div key={group.title} className="mb-4">
              {!collapsed && (
                <div className="px-4 mb-2 text-[10px] font-semibold tracking-wider text-gray-500 uppercase">
                  {group.title}
                </div>
              )}
              {group.items.map((item) => {
                const active = pathname === item.href || pathname.startsWith(item.href + "/");
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`
                      flex items-center gap-3 px-4 py-2 text-sm transition-colors
                      ${active ? "bg-gray-800 text-white border-l-2 border-blue-400" : "hover:bg-gray-800 hover:text-white"}
                      ${collapsed ? "justify-center" : ""}
                    `}
                    title={collapsed ? item.label : undefined}
                  >
                    <span className="text-base w-5 text-center">{item.icon}</span>
                    {!collapsed && <span>{item.label}</span>}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        {/* User section at bottom */}
        <div className="absolute bottom-0 left-0 right-0 border-t border-gray-700 p-4">
          <UserSection collapsed={collapsed} />
        </div>
      </aside>

      {/* Mobile overlay */}
      {!collapsed && (
        <div
          className="fixed inset-0 bg-black/50 z-30 md:hidden"
          onClick={() => setCollapsed(true)}
        />
      )}
    </>
  );
}
