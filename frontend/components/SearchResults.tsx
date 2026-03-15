"use client";

import { Button } from "@/components/ui/button";
import { ElementCard } from "@/components/ElementCard";
import { ErrorBanner } from "@/components/ErrorBanner";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { getElements } from "@/lib/api/elements";
import type { FilterState } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

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
  const router = useRouter();
  const [selected, setSelected] = useState<Set<string>>(new Set());

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

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else if (next.size < 2) {
        next.add(id);
      }
      return next;
    });
  }

  function handleCompare() {
    const ids = Array.from(selected);
    if (ids.length === 2) {
      router.push(`/compare?a=${ids[0]}&b=${ids[1]}`);
    }
  }

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
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {data.total} result{data.total !== 1 ? "s" : ""}
        </p>
        {selected.size === 2 && (
          <Button size="sm" onClick={handleCompare}>
            Compare selected
          </Button>
        )}
        {selected.size === 1 && (
          <p className="text-sm text-muted-foreground">
            Select one more element to compare
          </p>
        )}
      </div>
      <div className="space-y-3">
        {data.items.map((element) => (
          <div key={element.id} className="flex items-start gap-3">
            <input
              type="checkbox"
              checked={selected.has(element.id)}
              onChange={() => toggleSelect(element.id)}
              className="mt-4"
              aria-label={`Select ${element.name} for comparison`}
            />
            <div className="flex-1">
              <ElementCard element={element} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
