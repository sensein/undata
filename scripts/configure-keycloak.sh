#!/bin/sh
# Configure Keycloak Globus IdP with credentials from .env
# Run after: docker compose up -d
# Usage: ./scripts/configure-keycloak.sh

set -e

# Load .env
if [ -f .env ]; then
  export $(grep -v '^#' .env | grep -v '^\s*$' | xargs)
fi

if [ -z "$GLOBUS_CLIENT_ID" ] || [ -z "$GLOBUS_CLIENT_SECRET" ]; then
  echo "Error: GLOBUS_CLIENT_ID and GLOBUS_CLIENT_SECRET must be set in .env"
  exit 1
fi

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8080}"
REALM="undata"

echo "Waiting for Keycloak to be ready..."
until curl -sf "$KEYCLOAK_URL/realms/master" > /dev/null 2>&1; do
  sleep 2
done
echo "Keycloak is ready."

# Get admin token
TOKEN=$(curl -s "$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" \
  -d "username=admin" \
  -d "password=admin" \
  -d "grant_type=password" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

if [ -z "$TOKEN" ]; then
  echo "Error: Failed to get admin token"
  exit 1
fi

echo "Updating Globus IdP configuration..."

# Update the Globus identity provider with real credentials
curl -sf -X PUT "$KEYCLOAK_URL/admin/realms/$REALM/identity-provider/instances/globus" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"alias\": \"globus\",
    \"providerId\": \"oidc\",
    \"enabled\": true,
    \"displayName\": \"Globus (Institutional Login)\",
    \"config\": {
      \"clientId\": \"$GLOBUS_CLIENT_ID\",
      \"clientSecret\": \"$GLOBUS_CLIENT_SECRET\",
      \"authorizationUrl\": \"https://auth.globus.org/v2/oauth2/authorize\",
      \"tokenUrl\": \"https://auth.globus.org/v2/oauth2/token\",
      \"userInfoUrl\": \"https://auth.globus.org/v2/oauth2/userinfo\",
      \"jwksUrl\": \"https://auth.globus.org/jwk.json\",
      \"logoutUrl\": \"https://auth.globus.org/v2/web/logout\",
      \"defaultScope\": \"openid profile email\",
      \"clientAuthMethod\": \"client_secret_basic\",
      \"syncMode\": \"IMPORT\",
      \"trustEmail\": \"true\"
    }
  }"

echo ""
echo "Globus IdP configured successfully!"
echo "Sign in at: http://localhost:3000 → Sign in → Globus (Institutional Login)"
