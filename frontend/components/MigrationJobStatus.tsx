"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJobStatus } from "@/lib/api/migration";
import type { MigrationJob } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";

interface MigrationJobStatusProps {
  jobId: string;
  onComplete?: (job: MigrationJob) => void;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

const MAX_POLLS = 150; // 150 * 2s = 5 minutes

export function MigrationJobStatus({
  jobId,
  onComplete,
}: MigrationJobStatusProps) {
  const { data: job, error } = useQuery({
    queryKey: ["migration-job", jobId],
    queryFn: async () => {
      const result = await getJobStatus(jobId);
      if (
        (result.status === "completed" || result.status === "failed") &&
        onComplete
      ) {
        onComplete(result);
      }
      return result;
    },
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "completed" || status === "failed") return false;
      if (query.state.dataUpdateCount > MAX_POLLS) return false;
      return 2000;
    },
  });

  if (error) return <ErrorBanner error={error as Error} />;
  if (!job) return <p className="text-sm text-muted-foreground">Loading job status...</p>;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-3 text-base">
          Migration Job
          <Badge variant="outline" className={STATUS_COLORS[job.status] || ""}>
            {job.status}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="text-sm">
          <span className="text-muted-foreground">Job ID:</span>{" "}
          <code className="text-xs">{job.id}</code>
        </div>

        {job.status === "running" && (
          <div>
            <div className="mb-1 flex justify-between text-sm">
              <span>Progress</span>
              <span>{Math.round(job.progress * 100)}%</span>
            </div>
            <div className="h-2 rounded-full bg-muted">
              <div
                className="h-2 rounded-full bg-blue-500 transition-all"
                style={{ width: `${job.progress * 100}%` }}
              />
            </div>
          </div>
        )}

        {job.status === "failed" && job.error && (
          <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            {job.error}
          </div>
        )}

        {job.status === "completed" && job.output_data && (
          <div>
            <h4 className="mb-2 text-sm font-medium">Output</h4>
            <pre className="max-h-64 overflow-auto rounded bg-muted p-3 text-xs">
              {JSON.stringify(job.output_data, null, 2)}
            </pre>
          </div>
        )}

        {job.input_data && (
          <details className="text-sm">
            <summary className="cursor-pointer text-muted-foreground">
              Input data
            </summary>
            <pre className="mt-2 max-h-40 overflow-auto rounded bg-muted p-3 text-xs">
              {JSON.stringify(job.input_data, null, 2)}
            </pre>
          </details>
        )}
      </CardContent>
    </Card>
  );
}
