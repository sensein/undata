"use client";

import { FilterPanel } from "@/components/FilterPanel";
import { SearchBar } from "@/components/SearchBar";
import { SearchResults } from "@/components/SearchResults";
import type { FilterState } from "@/lib/types";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useState } from "react";

export function ElementsSearch() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const initialQuery = searchParams.get("q") || "";
  const [query, setQuery] = useState(initialQuery);
  const [filters, setFilters] = useState<FilterState>({
    source_id: searchParams.get("source") || null,
    data_type: searchParams.get("type") || null,
    has_aliases: searchParams.get("has_aliases") === "true" ? true : null,
    has_mappings: searchParams.get("has_mappings") === "true" ? true : null,
  });

  const offset = parseInt(searchParams.get("offset") || "0", 10);

  const syncUrl = useCallback(
    (q: string, f: FilterState) => {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (f.source_id) params.set("source", f.source_id);
      if (f.data_type) params.set("type", f.data_type);
      if (f.has_aliases) params.set("has_aliases", "true");
      if (f.has_mappings) params.set("has_mappings", "true");
      router.replace(`/elements?${params.toString()}`);
    },
    [router],
  );

  function handleSearch(q: string) {
    setQuery(q);
    syncUrl(q, filters);
  }

  function handleFilterChange(f: FilterState) {
    setFilters(f);
    syncUrl(query, f);
  }

  return (
    <div className="flex gap-8">
      <aside className="w-56 shrink-0">
        <FilterPanel filters={filters} onFilterChange={handleFilterChange} />
      </aside>
      <div className="flex-1">
        <SearchBar initialQuery={initialQuery} onSearch={handleSearch} />
        <div className="mt-6">
          <SearchResults query={query} filters={filters} offset={offset} />
        </div>
      </div>
    </div>
  );
}
