"use client";

import { useQuery } from "@apollo/client/react";
import { BROWSE_ELEMENTS, BROWSE_SCHEMAS, BROWSE_VALUES, BROWSE_VALUESETS } from "@/graphql/queries";
import { SourceBadge } from "@/components/SourceBadge";
import Link from "next/link";
import type { ElementConnection, SchemaConnection, ValueConnection, Connection, ValueSetNode } from "@/graphql/types";

const SOURCES = ["bids", "nwb", "dandi", "openminds", "aind", "reproschema", "nda", "openneuro"];

function SourceCard({ source }: { source: string }) {
  const { data: elemData } = useQuery<{ browseElements: ElementConnection }>(
    BROWSE_ELEMENTS,
    { variables: { source, first: 1 }, fetchPolicy: "no-cache" },
  );
  const { data: schemaData } = useQuery<{ browseSchemas: SchemaConnection }>(
    BROWSE_SCHEMAS,
    { variables: { source, first: 1 }, fetchPolicy: "no-cache" },
  );
  const { data: valueData } = useQuery<{ browseValues: ValueConnection }>(
    BROWSE_VALUES,
    { variables: { source, first: 1 }, fetchPolicy: "no-cache" },
  );
  const { data: valuesetData } = useQuery<{ browseValuesets: Connection<ValueSetNode> }>(
    BROWSE_VALUESETS,
    { variables: { source, first: 1 }, fetchPolicy: "no-cache" },
  );

  const counts = {
    elements: elemData?.browseElements?.totalCount ?? 0,
    schemas: schemaData?.browseSchemas?.totalCount ?? 0,
    values: valueData?.browseValues?.totalCount ?? 0,
    valuesets: valuesetData?.browseValuesets?.totalCount ?? 0,
  };

  const total = counts.elements + counts.schemas + counts.values + counts.valuesets;

  return (
    <Link href={`/sources/${source}`} className="block">
      <div className="border rounded-lg p-5 hover:shadow-md transition-shadow hover:border-blue-300">
        <div className="flex items-center gap-3 mb-3">
          <SourceBadge source={source} />
          <span className="text-sm text-gray-500">{total} entities</span>
        </div>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500">Elements</span>
            <span className="font-medium">{counts.elements}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Schemas</span>
            <span className="font-medium">{counts.schemas}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Values</span>
            <span className="font-medium">{counts.values}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Valuesets</span>
            <span className="font-medium">{counts.valuesets}</span>
          </div>
        </div>
      </div>
    </Link>
  );
}

export default function SourcesPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Sources</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {SOURCES.map((source) => (
          <SourceCard key={source} source={source} />
        ))}
      </div>
    </div>
  );
}
