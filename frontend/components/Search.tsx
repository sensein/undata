"use client";

import { useState } from "react";
import { useQuery } from "@apollo/client/react";
import { BROWSE_ELEMENTS, BROWSE_VALUES } from "@/graphql/queries";
import type { ElementEdge, ValueNode } from "@/graphql/types";

export function Search() {
  const [query, setQuery] = useState("");
  const [searchType, setSearchType] = useState<"elements" | "values">(
    "elements"
  );

  // Queries will be used when search index is available
  const _elemResult = useQuery<{
    browseElements: { edges: ElementEdge[]; totalCount: number };
  }>(BROWSE_ELEMENTS, {
    variables: { first: 10 },
    skip: searchType !== "elements" || !query,
  });

  const _valResult = useQuery<{ browseValues: ValueNode[] }>(BROWSE_VALUES, {
    variables: { first: 10 },
    skip: searchType !== "values" || !query,
  });

  return (
    <div className="w-full max-w-2xl">
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          className="flex-1 border rounded px-3 py-2"
          placeholder="Search entities..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          className="border rounded px-3 py-2"
          value={searchType}
          onChange={(e) =>
            setSearchType(e.target.value as "elements" | "values")
          }
        >
          <option value="elements">Elements</option>
          <option value="values">Values</option>
        </select>
      </div>

      {/* Results would be filtered client-side for now */}
      <p className="text-xs text-gray-500">
        Full-text search requires a search index (Meilisearch). For now, use
        source/type filters on the browse pages.
      </p>
    </div>
  );
}
