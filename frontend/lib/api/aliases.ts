import type { AliasGroupDetail } from "@/lib/types";
import { apiFetch } from "./client";

export async function getAliasGroup(id: string): Promise<AliasGroupDetail> {
  return apiFetch<AliasGroupDetail>(`/api/v1/aliases/${id}`);
}

export async function registerAlias(
  elementAId: string,
  elementBId: string,
): Promise<AliasGroupDetail> {
  return apiFetch<AliasGroupDetail>("/api/v1/aliases", {
    method: "POST",
    body: JSON.stringify({
      element_ids: [elementAId, elementBId],
      sssom_predicate: "skos:exactMatch",
    }),
  });
}
