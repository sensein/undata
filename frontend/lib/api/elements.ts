import type { DataElement, PaginatedList } from "@/lib/types";
import { apiFetch } from "./client";

export async function getElements(params: {
  q?: string;
  source?: string;
  source_id?: string;
  data_type?: string;
  ontology_term?: string;
  has_aliases?: boolean;
  has_mappings?: boolean;
  limit?: number;
  offset?: number;
}): Promise<PaginatedList<DataElement>> {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.source) query.set("source", params.source);
  if (params.source_id) query.set("source_id", params.source_id);
  if (params.data_type) query.set("data_type", params.data_type);
  if (params.ontology_term) query.set("ontology_term", params.ontology_term);
  if (params.limit) query.set("limit", String(params.limit));
  if (params.offset) query.set("offset", String(params.offset));

  return apiFetch<PaginatedList<DataElement>>(
    `/api/v1/elements?${query.toString()}`,
  );
}

export async function getElementByUri(
  uri: string,
): Promise<DataElement> {
  return apiFetch<DataElement>(`/api/v1/elements/${uri}`);
}

export async function createElement(payload: {
  semantic: { data_type: string; ontology_term?: string; unit?: string; constraints?: Record<string, unknown> };
  provenance: Array<{ source: string; class: string; name: string; description?: string }>;
}): Promise<DataElement> {
  return apiFetch<DataElement>("/api/v1/elements", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
