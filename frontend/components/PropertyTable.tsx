"use client";

import { useMemo } from "react";
import { useQuery } from "@apollo/client/react";
import { gql } from "@apollo/client";
import { createColumnHelper } from "@tanstack/react-table";
import { EntityDataGrid } from "@/components/EntityDataGrid";
import { EntityTag } from "@/components/EntityTag";
import { SourceBadge } from "@/components/SourceBadge";

// Per-sha256 queries for each entity type
const GET_ELEMENT = gql`
  query ResolveElement($sha256: String!) {
    element(sha256: $sha256) {
      sha256
      dataType
      unit
      provenance { source name }
    }
  }
`;

const GET_SCHEMA = gql`
  query ResolveSchema($sha256: String!) {
    schema_(sha256: $sha256) {
      sha256
      description
      provenance { source name }
    }
  }
`;

const GET_VALUE = gql`
  query ResolveValue($sha256: String!) {
    value(sha256: $sha256) {
      sha256
      label
      valueType
      provenance { source name }
    }
  }
`;

const GET_VALUESET = gql`
  query ResolveValueSet($sha256: String!) {
    valueset(sha256: $sha256) {
      sha256
      name
      provenance { source name }
    }
  }
`;

// Resolved entity — works for any type
interface ResolvedEntity {
  sha256: string;
  name: string;
  entityType: string; // "elements" | "schemas" | "values" | "valuesets"
  detail: string;     // dataType, label, description — depends on type
  source: string;
}

/**
 * Hook to resolve a list of sha256 hashes to entities by querying all types.
 * Uses the expected entity type first, falls back to others.
 */
function useResolveEntities(
  sha256List: string[],
  primaryType: "elements" | "values" | "schemas" | "valuesets" = "elements",
): Map<string, ResolvedEntity> {
  // Query all types for each sha256 — Apollo cache deduplicates
  const elementResults = sha256List.map((sha) => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const { data } = useQuery(GET_ELEMENT, {
      variables: { sha256: sha.slice(0, 12) },
      skip: !sha || sha.length < 12 || (primaryType !== "elements" && primaryType !== "schemas"),
    });
    return { sha, data };
  });

  const schemaResults = sha256List.map((sha) => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const { data } = useQuery(GET_SCHEMA, {
      variables: { sha256: sha.slice(0, 12) },
      skip: !sha || sha.length < 12,
    });
    return { sha, data };
  });

  const valueResults = sha256List.map((sha) => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const { data } = useQuery(GET_VALUE, {
      variables: { sha256: sha.slice(0, 12) },
      skip: !sha || sha.length < 12 || (primaryType !== "values" && primaryType !== "valuesets"),
    });
    return { sha, data };
  });

  const valuesetResults = sha256List.map((sha) => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const { data } = useQuery(GET_VALUESET, {
      variables: { sha256: sha.slice(0, 12) },
      skip: !sha || sha.length < 12 || primaryType !== "valuesets",
    });
    return { sha, data };
  });

  return useMemo(() => {
    const map = new Map<string, ResolvedEntity>();
    // Elements
    for (const { sha, data } of elementResults) {
      const e = data?.element;
      if (e && !map.has(sha)) {
        map.set(sha, {
          sha256: e.sha256,
          name: e.provenance?.[0]?.name ?? e.sha256.slice(0, 12),
          entityType: "elements",
          detail: [e.dataType, e.unit].filter(Boolean).join(" / ") || "",
          source: e.provenance?.[0]?.source ?? "",
        });
      }
    }
    // Schemas
    for (const { sha, data } of schemaResults) {
      const s = data?.schema_;
      if (s && !map.has(sha)) {
        map.set(sha, {
          sha256: s.sha256,
          name: s.provenance?.[0]?.name ?? s.sha256.slice(0, 12),
          entityType: "schemas",
          detail: s.description?.slice(0, 60) ?? "",
          source: s.provenance?.[0]?.source ?? "",
        });
      }
    }
    // Values
    for (const { sha, data } of valueResults) {
      const v = data?.value;
      if (v && !map.has(sha)) {
        map.set(sha, {
          sha256: v.sha256,
          name: v.label ?? v.provenance?.[0]?.name ?? v.sha256.slice(0, 12),
          entityType: "values",
          detail: v.valueType ?? "",
          source: v.provenance?.[0]?.source ?? "",
        });
      }
    }
    // Valuesets
    for (const { sha, data } of valuesetResults) {
      const vs = data?.valueset;
      if (vs && !map.has(sha)) {
        map.set(sha, {
          sha256: vs.sha256,
          name: vs.name ?? vs.provenance?.[0]?.name ?? vs.sha256.slice(0, 12),
          entityType: "valuesets",
          detail: "",
          source: vs.provenance?.[0]?.source ?? "",
        });
      }
    }
    return map;
  }, [elementResults, schemaResults, valueResults, valuesetResults]);
}

// --- Column definitions (shared) ---

const colHelper = createColumnHelper<ResolvedEntity | { raw: string }>();

const COLUMNS = [
  colHelper.display({
    id: "name",
    header: "Name",
    cell: (info) => {
      const row = info.row.original;
      if ("raw" in row) {
        return (
          <span className="font-mono text-xs text-gray-400">
            {String(row.raw).slice(0, 12)}
            <span className="text-[10px] bg-gray-100 px-1 rounded ml-1">unresolved</span>
          </span>
        );
      }
      return <EntityTag entityType={row.entityType} sha256={row.sha256} label={row.name} />;
    },
    sortingFn: (rowA, rowB) => {
      const get = (o: Record<string, unknown>) => String(o.raw ?? o.name ?? "");
      return get(rowA.original as Record<string, unknown>)
        .toLowerCase()
        .localeCompare(get(rowB.original as Record<string, unknown>).toLowerCase());
    },
    enableColumnFilter: false,
  }),
  colHelper.display({
    id: "detail",
    header: "Detail",
    cell: (info) => {
      const row = info.row.original;
      return "detail" in row ? <span className="font-mono text-xs">{row.detail || "—"}</span> : "—";
    },
    enableSorting: false,
    enableColumnFilter: false,
  }),
  colHelper.display({
    id: "type",
    header: "Entity Type",
    cell: (info) => {
      const row = info.row.original;
      if ("entityType" in row) {
        const labels: Record<string, string> = { elements: "element", schemas: "schema", values: "value", valuesets: "valueset" };
        return <span className="text-[10px] bg-gray-100 px-1.5 py-0.5 rounded">{labels[row.entityType] ?? row.entityType}</span>;
      }
      return "—";
    },
    enableSorting: false,
    enableColumnFilter: false,
  }),
  colHelper.display({
    id: "source",
    header: "Source",
    cell: (info) => {
      const row = info.row.original;
      return "source" in row && row.source ? <SourceBadge source={row.source} /> : "—";
    },
    enableSorting: false,
    enableColumnFilter: false,
  }),
];

// --- Element Property Table (for schema properties → can be elements or schemas) ---

interface ElementPropertyTableProps {
  properties: string[];
  schemaSource?: string;
}

export function ElementPropertyTable({ properties }: ElementPropertyTableProps) {
  const lookup = useResolveEntities(properties, "elements");

  const rows = useMemo(
    () => properties.map((ref) => lookup.get(ref) ?? { raw: ref }),
    [properties, lookup],
  );

  return (
    <div>
      <h3 className="text-sm font-semibold mb-2">Properties ({properties.length})</h3>
      <EntityDataGrid columns={COLUMNS} data={rows} totalCount={properties.length} />
    </div>
  );
}

// --- Value Member Table (for valueset members → values) ---

interface ValueMemberTableProps {
  members: string[];
}

export function ValueMemberTable({ members }: ValueMemberTableProps) {
  const lookup = useResolveEntities(members, "values");

  const rows = useMemo(
    () => members.map((ref) => lookup.get(ref) ?? { raw: ref }),
    [members, lookup],
  );

  return (
    <div>
      <h3 className="text-sm font-semibold mb-2">Members ({members.length})</h3>
      <EntityDataGrid columns={COLUMNS} data={rows} totalCount={members.length} />
    </div>
  );
}
