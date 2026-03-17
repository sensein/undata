"use client";

import { ErrorBanner } from "@/components/ErrorBanner";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { ValueConceptCard } from "@/components/ValueConceptCard";
import { apiFetch } from "@/lib/api/client";
import type { PaginatedList, ValueConceptResponse } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";

export default function ValuesPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["values"],
    queryFn: () =>
      apiFetch<PaginatedList<ValueConceptResponse>>("/api/v1/values"),
  });

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Value Concepts</h1>

      {isLoading && <LoadingSkeleton count={5} />}
      {error && <ErrorBanner error={error as Error} />}

      {data && data.items.length === 0 && (
        <p className="py-8 text-center text-muted-foreground">
          No value concepts found.
        </p>
      )}

      {data && (
        <div className="space-y-3">
          {data.items.map((v) => (
            <ValueConceptCard key={v.uri} value={v} />
          ))}
        </div>
      )}
    </div>
  );
}
