/**
 * Auth helpers — session management, sign in/out.
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8002";

export interface AuthUser {
  sub: string;
  email: string;
  name: string;
  roles: string[];
}

export async function getSession(): Promise<AuthUser | null> {
  try {
    const resp = await fetch(`${BACKEND_URL}/auth/me`, {
      credentials: "include",
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

export function signIn() {
  window.location.href = `${BACKEND_URL}/auth/login`;
}

export function signOut() {
  document.cookie = "access_token=; Max-Age=0; path=/";
  window.location.href = "/";
}

export function hasRole(user: AuthUser | null, role: string): boolean {
  if (!user) return false;
  const hierarchy: Record<string, number> = {
    admin: 4, curator: 3, contributor: 2, viewer: 1,
  };
  const required = hierarchy[role] ?? 0;
  return user.roles.some((r) => (hierarchy[r] ?? 0) >= required);
}
