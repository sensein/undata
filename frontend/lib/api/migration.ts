import type {
  MigrationJob,
  PaginatedList,
  PathwayDetail,
  PathwaySummary,
  SchemaDiffResult,
} from "@/lib/types";
import { ApiError } from "./client";

const MIGRATION_URL =
  typeof window === "undefined"
    ? process.env.MIGRATION_INTERNAL_URL ||
      process.env.NEXT_PUBLIC_MIGRATION_URL ||
      ""
    : process.env.NEXT_PUBLIC_MIGRATION_URL || "";

async function migrationFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${MIGRATION_URL}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };

  const token = process.env.API_TOKEN;
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch {
    throw new ApiError(503, "Migration service unavailable");
  }

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail?.message || body.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json() as Promise<T>;
}

export async function getPathways(): Promise<PaginatedList<PathwaySummary>> {
  return migrationFetch<PaginatedList<PathwaySummary>>("/api/v1/pathways");
}

export async function getPathway(id: string): Promise<PathwayDetail> {
  return migrationFetch<PathwayDetail>(`/api/v1/pathways/${id}`);
}

export async function executeMigration(
  pathwayId: string,
  inputData: Record<string, unknown>,
): Promise<MigrationJob> {
  return migrationFetch<MigrationJob>("/api/v1/migrations/execute", {
    method: "POST",
    body: JSON.stringify({ pathway_id: pathwayId, input_data: inputData }),
  });
}

export async function getJobStatus(jobId: string): Promise<MigrationJob> {
  return migrationFetch<MigrationJob>(`/api/v1/migrations/jobs/${jobId}`);
}

export async function getSchemaDiff(
  schemaAId: string,
  schemaBId: string,
): Promise<SchemaDiffResult> {
  return migrationFetch<SchemaDiffResult>(
    `/api/v1/schemas/diff?a=${schemaAId}&b=${schemaBId}`,
  );
}
