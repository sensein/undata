/**
 * Auth helpers — session management, sign in/out.
 * Token stored in localStorage after OAuth callback.
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8002";

export interface AuthUser {
  sub: string;
  email: string;
  name: string;
  roles: string[];
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

export async function getSession(): Promise<AuthUser | null> {
  const token = getToken();
  if (!token) return null;

  try {
    const resp = await fetch(`${BACKEND_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!resp.ok) {
      // Token expired or invalid — clear it
      if (resp.status === 401) localStorage.removeItem("access_token");
      return null;
    }
    return await resp.json();
  } catch {
    return null;
  }
}

export function signIn() {
  window.location.href = `${BACKEND_URL}/auth/login`;
}

export function signOut() {
  localStorage.removeItem("access_token");
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
