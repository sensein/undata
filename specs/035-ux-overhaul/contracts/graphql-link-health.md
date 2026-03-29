# GraphQL Contract: Link Health Monitoring

## Queries

```graphql
type Query {
  linkHealthStatus: LinkHealthDashboard!
  linkHealthChecks(
    checkType: String        # "domain" or "ontology_prefix"
    isHealthy: Boolean       # filter by health status
    first: Int = 50
  ): [LinkHealthCheck!]!
}

type LinkHealthDashboard {
  totalDomains: Int!
  healthyDomains: Int!
  unhealthyDomains: Int!
  totalPrefixes: Int!
  healthyPrefixes: Int!
  unhealthyPrefixes: Int!
  lastCheckAt: String
}

type LinkHealthCheck {
  id: ID!
  checkType: String!           # "domain" or "ontology_prefix"
  target: String!              # domain or prefix URL
  httpStatus: Int!
  redirectTarget: String
  isHealthy: Boolean!
  affectedEntityCount: Int!
  checkedAt: String!
}
```

## Background Task

- Runs daily (configurable via `LINK_CHECK_INTERVAL_HOURS` env var, default 24)
- Extracts distinct domains from `ontology_annotations[*].term_uri` across all entity tables
- Extracts ontology base-URI prefixes (URI up to last `_` or `#`)
- Performs HEAD request with 10s timeout, follows redirects
- Updates `link_health_checks` table (upsert by check_type+target)
- Creates curation flag (type "broken_link") for newly-detected failures
