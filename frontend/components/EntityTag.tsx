"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@apollo/client/react";
import { getEntityColor } from "@/lib/source-colors";
import { ELEMENT_POPOVER, SCHEMA_POPOVER, VALUE_POPOVER } from "@/graphql/queries";

const POPOVER_QUERIES: Record<string, ReturnType<typeof import("@apollo/client").gql>> = {
  elements: ELEMENT_POPOVER,
  schemas: SCHEMA_POPOVER,
  values: VALUE_POPOVER,
};

const ENTITY_PATHS: Record<string, string> = {
  elements: "/elements",
  schemas: "/schemas",
  values: "/values",
  valuesets: "/valuesets",
};

interface EntityTagProps {
  entityType: string;
  sha256: string;
  label: string;
  showPopover?: boolean;
}

function EntityPopover({ entityType, sha256 }: { entityType: string; sha256: string }) {
  const query = POPOVER_QUERIES[entityType];
  const { data, loading } = useQuery(query!, {
    variables: { sha256 },
    skip: !query,
    fetchPolicy: "cache-first",
  });

  if (loading) return <div className="p-2 text-xs text-gray-400">Loading...</div>;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const d = data as any;
  const entity = d?.element ?? d?.schema_ ?? d?.value;
  if (!entity) return null;

  const prov = entity.provenance?.[0];
  return (
    <div className="p-3 max-w-xs">
      <div className="font-medium text-sm mb-1">{prov?.name ?? entity.label ?? entity.sha256?.slice(0, 12)}</div>
      {entity.description && <div className="text-xs text-gray-600 mb-1">{entity.description}</div>}
      <div className="text-xs text-gray-400 space-x-2">
        {entity.dataType && <span>Type: {entity.dataType}</span>}
        {entity.unit && <span>Unit: {entity.unit}</span>}
        {entity.properties && <span>{entity.properties.length} properties</span>}
        {prov?.source && <span>Source: {prov.source}</span>}
      </div>
    </div>
  );
}

export function EntityTag({ entityType, sha256, label, showPopover = true }: EntityTagProps) {
  const [hovered, setHovered] = useState(false);
  const { bg, text } = getEntityColor(entityType);
  const path = ENTITY_PATHS[entityType] ?? "/elements";
  const hasPopover = showPopover && entityType in POPOVER_QUERIES;

  return (
    <span
      className="relative inline-block"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <Link
        href={`${path}/${sha256}`}
        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${bg} ${text} hover:opacity-80 transition-opacity`}
      >
        {label}
      </Link>
      {hasPopover && hovered && (
        <div className="absolute z-50 top-full left-0 mt-1 bg-white border rounded-lg shadow-lg min-w-48">
          <EntityPopover entityType={entityType} sha256={sha256} />
        </div>
      )}
    </span>
  );
}
