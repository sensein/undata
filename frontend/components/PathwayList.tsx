"use client";

import { ErrorBanner } from "@/components/ErrorBanner";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { PathwayCard } from "@/components/PathwayCard";
import { getPathways } from "@/lib/api/migration";
import { useQuery } from "@tanstack/react-query";

export function PathwayList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["pathways"],
    queryFn: getPathways,
  });

  if (isLoading) return <LoadingSkeleton count={3} />;
  if (error) return <ErrorBanner error={error as Error} />;

  if (!data || data.items.length === 0) {
    return (
      <p className="py-8 text-center text-muted-foreground">
        No migration pathways defined yet.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {data.items.map((pathway) => (
        <PathwayCard key={pathway.id} pathway={pathway} />
      ))}
    </div>
  );
}
