import type {
  CreateElementPayload,
  DataElementDetail,
  DataElementSummary,
  PaginatedList,
  SearchParams,
} from "@/lib/types";
import { apiFetch } from "./client";

export async function getElements(
  params: SearchParams,
): Promise<PaginatedList<DataElementSummary>> {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.source_id) query.set("source_id", params.source_id);
  if (params.data_type) query.set("data_type", params.data_type);
  if (params.has_aliases != null)
    query.set("has_aliases", String(params.has_aliases));
  if (params.has_mappings != null)
    query.set("has_mappings", String(params.has_mappings));
  if (params.limit) query.set("limit", String(params.limit));
  if (params.offset) query.set("offset", String(params.offset));

  return apiFetch<PaginatedList<DataElementSummary>>(
    `/api/v1/elements?${query.toString()}`,
  );
}

export async function getElementById(
  id: string,
): Promise<DataElementDetail> {
  return apiFetch<DataElementDetail>(`/api/v1/elements/${id}`);
}

export async function createElement(
  payload: CreateElementPayload,
): Promise<DataElementDetail> {
  return apiFetch<DataElementDetail>("/api/v1/elements", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
