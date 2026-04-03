"use client";

import { useState, useEffect } from "react";
import { useLazyQuery } from "@apollo/client/react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { SEARCH } from "@/graphql/queries";
import { EntityTag } from "@/components/EntityTag";
import { SourceBadge } from "@/components/SourceBadge";

interface SearchResult {
  entityType: string;
  sha256: string;
  name: string;
  source?: string;
  dataType?: string;
  unit?: string;
  description?: string;
  score: number;
}

const ENTITY_TYPE_LABELS: Record<string, string> = {
  element: "Elements",
  schema: "Schemas",
  value: "Values",
  valueset: "Value Sets",
};

const ENTITY_TYPE_PATHS: Record<string, string> = {
  element: "elements",
  schema: "schemas",
  value: "values",
  valueset: "valuesets",
};

type SearchModeType = "LEXICAL" | "SEMANTIC" | "BOTH";

function SearchContent() {
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q") ?? "";
  const [query, setQuery] = useState(initialQuery);
  const [mode, setMode] = useState<SearchModeType>("BOTH");
  const [executeSearch, { data, loading }] = useLazyQuery<{ search: SearchResult[] }>(SEARCH);

  const handleSearch = () => {
    if (query.trim()) {
      executeSearch({ variables: { query: query.trim(), mode, first: 100 } });
    }
  };

  // Auto-search on load if ?q= param present
  useEffect(() => {
    if (initialQuery) handleSearch();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  const results = data?.search ?? [];

  // Group by entity type
  const grouped: Record<string, SearchResult[]> = {};
  for (const r of results) {
    (grouped[r.entityType] ??= []).push(r);
  }

  return (
    <div>
      <h1 className="text-xl font-bold mb-4">Search</h1>

      <div className="flex gap-2 mb-3">
        <input
          type="text"
          className="border rounded px-3 py-2 text-sm flex-1"
          placeholder="Search across all entities (elements, schemas, values, valuesets)..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          autoFocus
        />
        <button
          onClick={handleSearch}
          className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
          disabled={loading}
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </div>

      <div className="flex gap-1 mb-6">
        {(["LEXICAL", "SEMANTIC", "BOTH"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-3 py-1 text-xs rounded border ${
              mode === m
                ? "bg-blue-600 text-white border-blue-600"
                : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
            }`}
          >
            {m === "LEXICAL" ? "Lexical" : m === "SEMANTIC" ? "Semantic" : "Both"}
          </button>
        ))}
        <span className="text-xs text-gray-400 ml-2 self-center">
          {mode === "LEXICAL" ? "Keyword matching" : mode === "SEMANTIC" ? "Meaning-based similarity" : "Combined search"}
        </span>
      </div>

      {results.length === 0 && data && !loading && (
        <p className="text-gray-500 text-sm">No results found for &ldquo;{query}&rdquo;</p>
      )}

      {Object.entries(grouped).map(([type, items]) => (
        <div key={type} className="mb-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-2 uppercase">
            {ENTITY_TYPE_LABELS[type] ?? type} ({items.length})
          </h2>
          <div className="border rounded overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b">
                  <th className="text-left px-2 py-1.5 font-medium text-xs">Name</th>
                  <th className="text-left px-2 py-1.5 font-medium text-xs">Source</th>
                  {type === "element" && <th className="text-left px-2 py-1.5 font-medium text-xs">Type</th>}
                  {type === "element" && <th className="text-left px-2 py-1.5 font-medium text-xs">Unit</th>}
                  <th className="text-left px-2 py-1.5 font-medium text-xs">Description</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={`${r.entityType}-${r.sha256}`} className="border-b hover:bg-gray-50">
                    <td className="px-2 py-1">
                      <EntityTag
                        entityType={ENTITY_TYPE_PATHS[r.entityType] ?? r.entityType}
                        sha256={r.sha256}
                        label={r.name}
                      />
                    </td>
                    <td className="px-2 py-1">
                      {r.source ? <SourceBadge source={r.source} /> : "—"}
                    </td>
                    {type === "element" && (
                      <td className="px-2 py-1 font-mono text-xs">{r.dataType ?? "—"}</td>
                    )}
                    {type === "element" && (
                      <td className="px-2 py-1 text-xs">{r.unit ?? "—"}</td>
                    )}
                    <td className="px-2 py-1 text-xs text-gray-500 truncate max-w-xs">
                      {r.description ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="p-8 text-gray-500">Loading search...</div>}>
      <SearchContent />
    </Suspense>
  );
}
