import { ApolloClient, InMemoryCache, HttpLink } from "@apollo/client";

const GRAPHQL_URL =
  process.env.NEXT_PUBLIC_GRAPHQL_URL || "http://localhost:8002/graphql";

// Shared merge function for cursor-based pagination
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function paginationMerge(existing: any, incoming: any) {
  if (!existing) return incoming;
  // Only merge if incoming has more edges (pagination), not fewer (different first)
  if (incoming.edges.length < existing.edges.length) return incoming;
  return {
    ...incoming,
    edges: [...existing.edges, ...incoming.edges],
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
            keyArgs: ["source", "dataType", "hasAnnotations", "searchText", "sortBy", "sortOrder", "first"],
            merge: paginationMerge,
          },
          browseSchemas: {
            keyArgs: ["source", "searchText", "first"],
            merge: paginationMerge,
          },
          browseValues: {
            keyArgs: ["source", "searchText", "first"],
            merge: paginationMerge,
          },
          browseValuesets: {
            keyArgs: ["source", "searchText", "first"],
            merge: paginationMerge,
          },
          browseTransforms: {
            keyArgs: ["sourceElement", "targetElement", "functionType", "first"],
            merge: paginationMerge,
          },
          curationQueue: {
            keyArgs: ["flagType", "status", "first"],
            merge: paginationMerge,
          },
        },
      },
    },
  }),
});
