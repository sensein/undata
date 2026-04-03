"use client";

import { useMemo } from "react";
import { useQuery } from "@apollo/client/react";
import { gql } from "@apollo/client";
import { createColumnHelper } from "@tanstack/react-table";
import { EntityDataGrid } from "@/components/EntityDataGrid";
import { EntityTag } from "@/components/EntityTag";
import { SourceBadge } from "@/components/SourceBadge";

// Query to resolve a batch of sha256 hashes to element details
const GET_ELEMENTS_BY_SHA = gql`
  query GetElementsBySha($sha256: String!) {
    element(sha256: $sha256) {
      sha256
      dataType
      unit
      provenance {
        source
        name
      }
    }
  }
`;

const GET_VALUE_BY_SHA = gql`
  query GetValueBySha($sha256: String!) {
    value(sha256: $sha256) {
      sha256
      label
      valueType
      provenance {
        source
        name
      }
    }
  }
`;

// --- Element Property Table (for schema properties) ---

interface ResolvedElement {
  sha256: string;
  name: string;
  dataType: string;
  unit: string;
  source: string;
}

interface ElementPropertyTableProps {
  properties: string[];
  schemaSource?: string;
}

const elemColHelper = createColumnHelper<ResolvedElement | { raw: string }>();

function useResolveElements(sha256List: string[]): Map<string, ResolvedElement> {
  // Query each sha256 individually using Apollo's cache
  const results = sha256List.map((sha) => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const { data } = useQuery(GET_ELEMENTS_BY_SHA, {
      variables: { sha256: sha.slice(0, 12) },
      skip: !sha || sha.length < 12,
    });
    return { sha, data };
  });

  return useMemo(() => {
    const map = new Map<string, ResolvedElement>();
    for (const { sha, data } of results) {
      const e = data?.element;
      if (e) {
        map.set(sha, {
          sha256: e.sha256,
          name: e.provenance?.[0]?.name ?? e.sha256.slice(0, 12),
          dataType: e.dataType ?? "",
          unit: e.unit ?? "",
          source: e.provenance?.[0]?.source ?? "",
        });
      }
    }
    return map;
  }, [results]);
}

export function ElementPropertyTable({ properties }: ElementPropertyTableProps) {
  const lookup = useResolveElements(properties);

  const rows = useMemo(() => {
    return properties.map((ref) => {
      const resolved = lookup.get(ref);
      return resolved ?? { raw: ref };
    });
  }, [properties, lookup]);

  const columns = useMemo(
    () => [
      elemColHelper.display({
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
          return <EntityTag entityType="elements" sha256={row.sha256} label={row.name} />;
        },
        sortingFn: (rowA, rowB) => {
          const get = (o: Record<string, unknown>) => String(o.raw ?? o.name ?? "");
          return get(rowA.original as Record<string, unknown>)
            .toLowerCase()
            .localeCompare(get(rowB.original as Record<string, unknown>).toLowerCase());
        },
        enableColumnFilter: false,
      }),
      elemColHelper.display({
        id: "dataType",
        header: "Type",
        cell: (info) => {
          const row = info.row.original;
          return "dataType" in row ? <span className="font-mono text-xs">{row.dataType || "—"}</span> : "—";
        },
        enableSorting: false,
        enableColumnFilter: false,
      }),
      elemColHelper.display({
        id: "unit",
        header: "Unit",
        cell: (info) => {
          const row = info.row.original;
          return "unit" in row && row.unit ? <span className="text-xs">{row.unit}</span> : "—";
        },
        enableSorting: false,
        enableColumnFilter: false,
      }),
      elemColHelper.display({
        id: "source",
        header: "Source",
        cell: (info) => {
          const row = info.row.original;
          return "source" in row && row.source ? <SourceBadge source={row.source} /> : "—";
        },
        enableSorting: false,
        enableColumnFilter: false,
      }),
    ],
    [],
  );

  return (
    <div>
      <h3 className="text-sm font-semibold mb-2">Properties ({properties.length})</h3>
      <EntityDataGrid columns={columns} data={rows} totalCount={properties.length} />
    </div>
  );
}

// --- Value Member Table (for valueset members) ---

interface ResolvedValue {
  sha256: string;
  label: string;
  valueType: string;
  source: string;
}

interface ValueMemberTableProps {
  members: string[];
}

const valColHelper = createColumnHelper<ResolvedValue | { raw: string }>();

function useResolveValues(sha256List: string[]): Map<string, ResolvedValue> {
  const results = sha256List.map((sha) => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const { data } = useQuery(GET_VALUE_BY_SHA, {
      variables: { sha256: sha.slice(0, 12) },
      skip: !sha || sha.length < 12,
    });
    return { sha, data };
  });

  return useMemo(() => {
    const map = new Map<string, ResolvedValue>();
    for (const { sha, data } of results) {
      const v = data?.value;
      if (v) {
        map.set(sha, {
          sha256: v.sha256,
          label: v.label ?? v.provenance?.[0]?.name ?? v.sha256.slice(0, 12),
          valueType: v.valueType ?? "",
          source: v.provenance?.[0]?.source ?? "",
        });
      }
    }
    return map;
  }, [results]);
}

export function ValueMemberTable({ members }: ValueMemberTableProps) {
  const lookup = useResolveValues(members);

  const rows = useMemo(() => {
    return members.map((ref) => {
      const resolved = lookup.get(ref);
      return resolved ?? { raw: ref };
    });
  }, [members, lookup]);

  const columns = useMemo(
    () => [
      valColHelper.display({
        id: "label",
        header: "Value",
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
          return <EntityTag entityType="values" sha256={row.sha256} label={row.label} />;
        },
        sortingFn: (rowA, rowB) => {
          const get = (o: Record<string, unknown>) => String(o.raw ?? o.label ?? "");
          return get(rowA.original as Record<string, unknown>)
            .toLowerCase()
            .localeCompare(get(rowB.original as Record<string, unknown>).toLowerCase());
        },
        enableColumnFilter: false,
      }),
      valColHelper.display({
        id: "valueType",
        header: "Type",
        cell: (info) => {
          const row = info.row.original;
          return "valueType" in row ? <span className="font-mono text-xs">{row.valueType || "—"}</span> : "—";
        },
        enableSorting: false,
        enableColumnFilter: false,
      }),
      valColHelper.display({
        id: "source",
        header: "Source",
        cell: (info) => {
          const row = info.row.original;
          return "source" in row && row.source ? <SourceBadge source={row.source} /> : "—";
        },
        enableSorting: false,
        enableColumnFilter: false,
      }),
    ],
    [],
  );

  return (
    <div>
      <h3 className="text-sm font-semibold mb-2">Members ({members.length})</h3>
      <EntityDataGrid columns={columns} data={rows} totalCount={members.length} />
    </div>
  );
}
