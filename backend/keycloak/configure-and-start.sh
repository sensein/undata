#!/bin/bash
set -e

REALM_FILE="/opt/keycloak/data/import/realm-export.json"

if [ -n "$GLOBUS_CLIENT_ID" ] && [ -n "$GLOBUS_CLIENT_SECRET" ]; then
  echo "Configuring Globus IdP with credentials from environment..."
  sed -i "s|PLACEHOLDER_GLOBUS_CLIENT_ID|${GLOBUS_CLIENT_ID}|g" "$REALM_FILE"
  sed -i "s|PLACEHOLDER_GLOBUS_CLIENT_SECRET|${GLOBUS_CLIENT_SECRET}|g" "$REALM_FILE"
  echo "Globus IdP credentials injected."
else
  echo "No GLOBUS_CLIENT_ID/SECRET — Globus IdP will have placeholder credentials."
fi

exec /opt/keycloak/bin/kc.sh start-dev --import-realm --hostname-strict=false --http-enabled=true --hostname=localhost
