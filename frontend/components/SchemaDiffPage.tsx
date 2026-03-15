"use client";

import { ErrorBanner } from "@/components/ErrorBanner";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { SchemaDiff } from "@/components/SchemaDiff";
import { getSchemaDiff } from "@/lib/api/migration";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

export function SchemaDiffPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const initialA = searchParams.get("a") || "";
  const initialB = searchParams.get("b") || "";

  const [schemaA, setSchemaA] = useState(initialA);
  const [schemaB, setSchemaB] = useState(initialB);

  const enabled = !!initialA && !!initialB;

  const { data: diff, isLoading, error } = useQuery({
    queryKey: ["schema-diff", initialA, initialB],
    queryFn: () => getSchemaDiff(initialA, initialB),
    enabled,
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (schemaA && schemaB) {
      router.push(`/migrations/diff?a=${schemaA}&b=${schemaB}`);
    }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="flex items-end gap-3">
        <div className="flex-1">
          <Label htmlFor="schema-a">Schema A (UUID)</Label>
          <Input
            id="schema-a"
            value={schemaA}
            onChange={(e) => setSchemaA(e.target.value)}
            placeholder="Schema UUID"
          />
        </div>
        <div className="flex-1">
          <Label htmlFor="schema-b">Schema B (UUID)</Label>
          <Input
            id="schema-b"
            value={schemaB}
            onChange={(e) => setSchemaB(e.target.value)}
            placeholder="Schema UUID"
          />
        </div>
        <Button type="submit" disabled={!schemaA || !schemaB}>
          Compare
        </Button>
      </form>

      {isLoading && <LoadingSkeleton count={3} />}
      {error && <ErrorBanner error={error as Error} />}
      {diff && <SchemaDiff diff={diff} />}

      {!enabled && !isLoading && (
        <p className="py-8 text-center text-muted-foreground">
          Enter two schema UUIDs to compare.
        </p>
      )}
    </div>
  );
}
