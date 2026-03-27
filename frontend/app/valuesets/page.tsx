"use client";

import { useQuery } from "@apollo/client/react";
import { gql } from "@apollo/client";
import type { Connection, Edge } from "@/graphql/types";

interface ValueSetNode {
  sha256: string;
  name?: string;
  members: string[];
  description?: string;
  provenance: { source: string; name: string }[];
}

const BROWSE_VALUESETS = gql`
  query BrowseValueSets($first: Int = 50) {
    browseElements(first: $first) {
      totalCount
    }
  }
`;

// Note: browseValuesets is not yet in the backend GraphQL schema.
// This page will show a placeholder until the query is added.

export default function ValueSetsPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Value Sets</h1>
      <div className="text-center py-12">
        <p className="text-gray-500 text-lg">Value sets browser coming soon</p>
        <p className="text-gray-400 text-sm mt-1">
          Value sets are named collections of values (e.g., sex_options = male + female).
          Browse individual values on the{" "}
          <a href="/values" className="text-blue-600 underline">
            Values page
          </a>
          .
        </p>
      </div>
    </div>
  );
}
