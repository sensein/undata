import type { MappingRef, PaginatedList } from "@/lib/types";
import { apiFetch } from "./client";

export async function getMappings(params: {
  source_element_id?: string;
  target_element_id?: string;
}): Promise<PaginatedList<MappingRef>> {
  const query = new URLSearchParams();
  if (params.source_element_id)
    query.set("source_element_id", params.source_element_id);
  if (params.target_element_id)
    query.set("target_element_id", params.target_element_id);

  return apiFetch<PaginatedList<MappingRef>>(
    `/api/v1/mappings?${query.toString()}`,
  );
}
