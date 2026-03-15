/**
 * Keycloak OIDC authentication helpers.
 *
 * Flow:
 * 1. User clicks "Sign in" → redirect to Keycloak authorize endpoint
 * 2. Keycloak redirects back to /auth/callback with ?code=
 * 3. Callback exchanges code for token, stores in httpOnly cookie
 * 4. Subsequent requests read token from cookie via middleware
 */

const KEYCLOAK_URL = process.env.KEYCLOAK_URL || "http://localhost:8080";
const KEYCLOAK_REALM = process.env.KEYCLOAK_REALM || "undata";
const KEYCLOAK_CLIENT_ID = process.env.KEYCLOAK_CLIENT_ID || "frontend";
const KEYCLOAK_CLIENT_SECRET = process.env.KEYCLOAK_CLIENT_SECRET || "";
const APP_URL = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

export function getAuthorizeUrl(): string {
  const params = new URLSearchParams({
    client_id: KEYCLOAK_CLIENT_ID,
    response_type: "code",
    scope: "openid profile email",
    redirect_uri: `${APP_URL}/auth/callback`,
  });
  return `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/auth?${params}`;
}

export async function exchangeCodeForToken(
  code: string,
): Promise<{ access_token: string; refresh_token: string; expires_in: number }> {
  const tokenUrl = `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/token`;
  const resp = await fetch(tokenUrl, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: KEYCLOAK_CLIENT_ID,
      client_secret: KEYCLOAK_CLIENT_SECRET,
      code,
      redirect_uri: `${APP_URL}/auth/callback`,
    }),
  });

  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`Token exchange failed: ${resp.status} ${body}`);
  }

  return resp.json();
}

export function getLogoutUrl(): string {
  const params = new URLSearchParams({
    client_id: KEYCLOAK_CLIENT_ID,
    post_logout_redirect_uri: APP_URL,
  });
  return `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/logout?${params}`;
}
