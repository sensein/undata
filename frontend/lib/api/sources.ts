import { apiFetch } from "./client";

export async function getSources(): Promise<
  Array<{ id: string; name: string }>
> {
  const result = await apiFetch<{
    items: Array<{ id: string; name: string }>;
  }>("/api/v1/sources");
  return result.items;
}
