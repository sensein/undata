"use client";

import { ElementCard } from "@/components/ElementCard";
import { ErrorBanner } from "@/components/ErrorBanner";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { getElements } from "@/lib/api/elements";
import type { FilterState } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";

interface SearchResultsProps {
  query: string;
  filters: FilterState;
  offset?: number;
}

export function SearchResults({
  query,
  filters,
  offset = 0,
}: SearchResultsProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["elements", query, filters, offset],
    queryFn: () =>
      getElements({
        q: query || undefined,
        source_id: filters.source_id || undefined,
        data_type: filters.data_type || undefined,
        has_aliases: filters.has_aliases ?? undefined,
        has_mappings: filters.has_mappings ?? undefined,
        offset,
        limit: 20,
      }),
  });

  if (isLoading) return <LoadingSkeleton count={5} />;
  if (error) return <ErrorBanner error={error as Error} />;

  if (!data || data.items.length === 0) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        <p className="text-lg">No results found</p>
        <p className="mt-1 text-sm">
          Try broadening your query or{" "}
          <a href="/add" className="underline">
            contribute a new element
          </a>
          .
        </p>
      </div>
    );
  }

  return (
    <div>
      <p className="mb-4 text-sm text-muted-foreground">
        {data.total} result{data.total !== 1 ? "s" : ""}
      </p>
      <div className="space-y-3">
        {data.items.map((element) => (
          <ElementCard key={element.id} element={element} />
        ))}
      </div>
    </div>
  );
}
