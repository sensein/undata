"use client";

import { useMemo } from "react";
import { useQuery } from "@apollo/client/react";
import { createColumnHelper } from "@tanstack/react-table";
import { EntityDataGrid } from "@/components/EntityDataGrid";
import { EntityTag } from "@/components/EntityTag";
import { SourceBadge } from "@/components/SourceBadge";
import { BROWSE_ELEMENTS, BROWSE_VALUES } from "@/graphql/queries";
import type { ElementConnection, ElementNode, ValueConnection, ValueNode, Edge } from "@/graphql/types";

// --- Element Property Table (for schema properties) ---

interface ElementPropertyTableProps {
  properties: string[];
  schemaSource?: string;
}

interface ResolvedElement {
  sha256: string;
  name: string;
  dataType: string;
  unit: string;
  source: string;
}

const elemColHelper = createColumnHelper<ResolvedElement | { raw: string }>();

export function ElementPropertyTable({ properties, schemaSource }: ElementPropertyTableProps) {
  const { data: elemData } = useQuery<{ browseElements: ElementConnection }>(BROWSE_ELEMENTS, {
    variables: { first: 2000 },
  });

  const lookup = useMemo(() => {
    const map = new Map<string, ResolvedElement>();
    for (const edge of (elemData?.browseElements?.edges ?? []) as Edge<ElementNode>[]) {
      const e = edge.node;
      const info: ResolvedElement = {
        sha256: e.sha256,
        name: e.provenance?.[0]?.name ?? e.sha256.slice(0, 12),
        dataType: e.dataType ?? "",
        unit: e.unit ?? "",
        source: e.provenance?.[0]?.source ?? "",
      };
      map.set(e.sha256, info);
      map.set(e.sha256.slice(0, 12), info);
      for (const prov of e.provenance ?? []) {
        if (prov.name) {
          const existing = map.get(prov.name);
          // Index by name — prefer element from same source as the schema
          if (!existing || (prov.source === schemaSource && existing.source !== schemaSource)) {
            map.set(prov.name, { ...info, name: prov.name, source: prov.source });
          }
          if (!map.has(prov.name.toLowerCase())) {
            map.set(prov.name.toLowerCase(), { ...info, name: prov.name, source: prov.source });
          }
        }
      }
    }
    return map;
  }, [elemData, schemaSource]);

  const rows = useMemo(() => {
    return properties.map((ref) => {
      const resolved = lookup.get(ref) || lookup.get(ref.slice(0, 12)) || lookup.get(ref.toLowerCase());
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
            return <span className="font-mono text-xs text-gray-400">{row.raw} <span className="text-[10px] bg-gray-100 px-1 rounded">unresolved</span></span>;
          }
          return <EntityTag entityType="elements" sha256={row.sha256} label={row.name} />;
        },
        sortingFn: (rowA, rowB) => {
          const get = (o: Record<string, unknown>) => String(o.raw ?? o.name ?? o.label ?? "");
          return get(rowA.original as Record<string, unknown>).toLowerCase().localeCompare(get(rowB.original as Record<string, unknown>).toLowerCase());
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

interface ValueMemberTableProps {
  members: string[];
}

interface ResolvedValue {
  sha256: string;
  label: string;
  valueType: string;
  source: string;
}

const valColHelper = createColumnHelper<ResolvedValue | { raw: string }>();

export function ValueMemberTable({ members }: ValueMemberTableProps) {
  const { data: valData } = useQuery<{ browseValues: ValueConnection }>(BROWSE_VALUES, {
    variables: { first: 2000 },
  });

  const lookup = useMemo(() => {
    const map = new Map<string, ResolvedValue>();
    for (const edge of (valData?.browseValues?.edges ?? []) as Edge<ValueNode>[]) {
      const v = edge.node;
      const info: ResolvedValue = {
        sha256: v.sha256,
        label: v.label ?? v.sha256.slice(0, 12),
        valueType: v.valueType ?? "",
        source: v.provenance?.[0]?.source ?? "",
      };
      map.set(v.sha256, info);
      map.set(v.sha256.slice(0, 12), info);
      if (v.label) {
        map.set(v.label, info);
        map.set(v.label.toLowerCase(), info);
      }
      for (const prov of v.provenance ?? []) {
        if (prov.name && !map.has(prov.name)) {
          map.set(prov.name, { ...info, label: prov.name });
          map.set(prov.name.toLowerCase(), { ...info, label: prov.name });
        }
      }
    }
    return map;
  }, [valData]);

  const rows = useMemo(() => {
    return members.map((ref) => {
      const resolved = lookup.get(ref) || lookup.get(ref.slice(0, 12)) || lookup.get(ref.toLowerCase()) || lookup.get(ref.replace(/_/g, " ").toLowerCase());
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
            return <span className="font-mono text-xs text-gray-400">{row.raw} <span className="text-[10px] bg-gray-100 px-1 rounded">unresolved</span></span>;
          }
          return <EntityTag entityType="values" sha256={row.sha256} label={row.label} />;
        },
        sortingFn: (rowA, rowB) => {
          const get = (o: Record<string, unknown>) => String(o.raw ?? o.name ?? o.label ?? "");
          return get(rowA.original as Record<string, unknown>).toLowerCase().localeCompare(get(rowB.original as Record<string, unknown>).toLowerCase());
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
