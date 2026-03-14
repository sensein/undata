"use client";

import { ComparisonView } from "@/components/ComparisonView";
import { ErrorBanner } from "@/components/ErrorBanner";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { getElementById } from "@/lib/api/elements";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";

export function ComparisonPage() {
  const searchParams = useSearchParams();
  const idA = searchParams.get("a");
  const idB = searchParams.get("b");

  const {
    data: elementA,
    isLoading: loadingA,
    error: errorA,
  } = useQuery({
    queryKey: ["element", idA],
    queryFn: () => getElementById(idA!),
    enabled: !!idA,
  });

  const {
    data: elementB,
    isLoading: loadingB,
    error: errorB,
  } = useQuery({
    queryKey: ["element", idB],
    queryFn: () => getElementById(idB!),
    enabled: !!idB,
  });

  if (!idA || !idB) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        <p className="text-lg">Select two elements to compare</p>
        <p className="mt-1 text-sm">
          Use the checkboxes on the{" "}
          <a href="/elements" className="underline">
            search page
          </a>{" "}
          to pick two elements.
        </p>
      </div>
    );
  }

  if (loadingA || loadingB) return <LoadingSkeleton count={3} />;
  if (errorA) return <ErrorBanner error={errorA as Error} />;
  if (errorB) return <ErrorBanner error={errorB as Error} />;
  if (!elementA || !elementB) return null;

  return <ComparisonView elementA={elementA} elementB={elementB} />;
}
