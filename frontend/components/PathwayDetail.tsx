"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { ErrorBanner } from "@/components/ErrorBanner";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { MigrationJobStatus } from "@/components/MigrationJobStatus";
import { executeMigration, getPathway } from "@/lib/api/migration";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

interface PathwayDetailProps {
  pathwayId: string;
}

export function PathwayDetail({ pathwayId }: PathwayDetailProps) {
  const [inputJson, setInputJson] = useState("{}");
  const [jobId, setJobId] = useState<string | null>(null);

  const { data: pathway, isLoading, error } = useQuery({
    queryKey: ["pathway", pathwayId],
    queryFn: () => getPathway(pathwayId),
  });

  const runMutation = useMutation({
    mutationFn: () => {
      const parsed = JSON.parse(inputJson);
      return executeMigration(pathwayId, parsed);
    },
    onSuccess: (job) => setJobId(job.id),
  });

  if (isLoading) return <LoadingSkeleton count={3} />;
  if (error) return <ErrorBanner error={error as Error} />;
  if (!pathway) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">
          {pathway.source_schema.name} &rarr; {pathway.target_schema.name}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {pathway.step_count} step{pathway.step_count !== 1 ? "s" : ""} &middot;
          Created {new Date(pathway.created_at).toLocaleDateString()}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Transformation Steps</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {pathway.steps.map((step) => (
              <div key={step.position} className="flex items-start gap-3 rounded border p-3">
                <Badge variant="outline" className="shrink-0">
                  #{step.position + 1}
                </Badge>
                <div className="text-sm">
                  <div>
                    <span className="text-muted-foreground">
                      {step.input_element}
                    </span>
                    {" "}&rarr;{" "}
                    <span>{step.output_element}</span>
                  </div>
                  <div className="mt-1 flex gap-2">
                    <Badge variant="secondary">{step.function_type}</Badge>
                    {step.expression && (
                      <code className="rounded bg-muted px-2 py-0.5 text-xs">
                        {step.expression}
                      </code>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Run Migration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <label htmlFor="input-json" className="mb-1 block text-sm font-medium">
              Input JSON
            </label>
            <Textarea
              id="input-json"
              value={inputJson}
              onChange={(e) => setInputJson(e.target.value)}
              rows={6}
              className="font-mono text-xs"
              placeholder='{"field": "value"}'
            />
          </div>

          {runMutation.error && (
            <ErrorBanner error={runMutation.error as Error} />
          )}

          <Button
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending || !!jobId}
          >
            {runMutation.isPending ? "Submitting..." : "Run Migration"}
          </Button>
        </CardContent>
      </Card>

      {jobId && <MigrationJobStatus jobId={jobId} />}
    </div>
  );
}
