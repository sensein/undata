/**
 * Index all data elements from the backend into Meilisearch.
 *
 * Usage: pnpm run index-elements
 *
 * Requires NEXT_PUBLIC_BACKEND_URL and NEXT_PUBLIC_MEILI_URL env vars.
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8002";
const MEILI_URL = process.env.NEXT_PUBLIC_MEILI_URL || "http://localhost:7700";
const MEILI_KEY = process.env.MEILI_MASTER_KEY || "";
const PAGE_SIZE = 100;

interface Element {
  id: string;
  name: string;
  data_type: string;
  description: string;
  source: { id: string; name: string };
}

async function fetchPage(offset: number): Promise<{ items: Element[]; total: number }> {
  const url = `${BACKEND_URL}/api/v1/elements?limit=${PAGE_SIZE}&offset=${offset}`;
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Backend returned ${resp.status}`);
  return resp.json();
}

async function upsertDocuments(docs: Array<Record<string, unknown>>) {
  const resp = await fetch(`${MEILI_URL}/indexes/elements/documents`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(MEILI_KEY ? { Authorization: `Bearer ${MEILI_KEY}` } : {}),
    },
    body: JSON.stringify(docs),
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`Meilisearch returned ${resp.status}: ${body}`);
  }
  return resp.json();
}

async function main() {
  console.log(`Indexing elements from ${BACKEND_URL} into ${MEILI_URL}...`);

  let offset = 0;
  let total = 0;
  let indexed = 0;

  do {
    const page = await fetchPage(offset);
    total = page.total;

    if (page.items.length === 0) break;

    const docs = page.items.map((el) => ({
      id: el.id,
      name: el.name,
      data_type: el.data_type,
      description: el.description,
      source_name: el.source.name,
    }));

    await upsertDocuments(docs);
    indexed += docs.length;
    offset += PAGE_SIZE;

    console.log(`  Indexed ${indexed}/${total} elements`);
  } while (offset < total);

  console.log(`Done. ${indexed} elements indexed.`);
}

main().catch((err) => {
  console.error("Indexing failed:", err);
  process.exit(1);
});
