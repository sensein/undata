import { ApolloClient, InMemoryCache, HttpLink } from "@apollo/client";

const GRAPHQL_URL =
  process.env.NEXT_PUBLIC_GRAPHQL_URL || "http://localhost:8002/graphql";

// Merge function for cursor-based pagination — append new edges
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function paginationMerge(existing: any, incoming: any) {
  if (!existing) return incoming;
  // If incoming has `after` cursor, it's a fetchMore — append edges
  // Otherwise it's a fresh query (filter change) — replace
  const existingCursors = new Set(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (existing.edges ?? []).map((e: any) => e.cursor),
  );
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const newEdges = (incoming.edges ?? []).filter((e: any) => !existingCursors.has(e.cursor));

  if (newEdges.length === 0 && incoming.edges.length > 0) {
    // All edges already exist — this is a duplicate fetch, return incoming
    return incoming;
  }

  return {
    ...incoming,
    edges: [...existing.edges, ...newEdges],
  };
}

export const apolloClient = new ApolloClient({
  link: new HttpLink({
    uri: GRAPHQL_URL,
  }),
  cache: new InMemoryCache({
    typePolicies: {
      Query: {
        fields: {
          browseElements: {
            keyArgs: ["source", "dataType", "hasAnnotations", "searchText", "sortBy", "sortOrder"],
            merge: paginationMerge,
          },
          browseSchemas: {
            keyArgs: ["source", "searchText"],
            merge: paginationMerge,
          },
          browseValues: {
            keyArgs: ["source", "searchText"],
            merge: paginationMerge,
          },
          browseValuesets: {
            keyArgs: ["source", "searchText"],
            merge: paginationMerge,
          },
          browseTransforms: {
            keyArgs: ["sourceElement", "targetElement", "functionType"],
            merge: paginationMerge,
          },
          curationQueue: {
            keyArgs: ["flagType", "status"],
            merge: paginationMerge,
          },
        },
      },
    },
  }),
});
