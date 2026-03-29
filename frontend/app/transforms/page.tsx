"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@apollo/client/react";
import { createColumnHelper } from "@tanstack/react-table";
import { BROWSE_TRANSFORMS } from "@/graphql/queries";
import { EntityDataGrid } from "@/components/EntityDataGrid";
import { EntityTag } from "@/components/EntityTag";
import type { TransformNode, Edge, Connection } from "@/graphql/types";

const columnHelper = createColumnHelper<TransformNode>();

export default function TransformsPage() {
  const [functionType, setFunctionType] = useState<string | undefined>();

  const { data, loading, error, fetchMore } = useQuery<{
    browseTransforms: Connection<TransformNode>;
  }>(BROWSE_TRANSFORMS, {
    variables: { functionType, first: 50 },
  });

  const transforms = useMemo(
    () => (data?.browseTransforms?.edges ?? []).map((e: Edge<TransformNode>) => e.node),
    [data],
  );
  const pageInfo = data?.browseTransforms?.pageInfo;
  const totalCount = data?.browseTransforms?.totalCount ?? 0;

  const columns = useMemo(
    () => [
      columnHelper.accessor("sourceElement", {
        header: "Source Element",
        cell: (info) => {
          const val = info.getValue();
          // Extract sha256 from URI or use directly
          const sha = val.includes("/") ? val.split("/").pop()! : val;
          const shortKey = sha.includes("_") ? sha.split("_").pop()! : sha.slice(0, 12);
          const name = sha.includes("_") ? sha.split("_")[0] : sha.slice(0, 12);
          return <EntityTag entityType="elements" sha256={shortKey} label={name} />;
        },
        enableColumnFilter: false,
      }),
      columnHelper.display({
        id: "arrow",
        header: "",
        cell: () => <span className="text-gray-400 text-lg">→</span>,
        enableSorting: false,
        enableColumnFilter: false,
      }),
      columnHelper.accessor("targetElement", {
        header: "Target Element",
        cell: (info) => {
          const val = info.getValue();
          const sha = val.includes("/") ? val.split("/").pop()! : val;
          const shortKey = sha.includes("_") ? sha.split("_").pop()! : sha.slice(0, 12);
          const name = sha.includes("_") ? sha.split("_")[0] : sha.slice(0, 12);
          return <EntityTag entityType="elements" sha256={shortKey} label={name} />;
        },
        enableColumnFilter: false,
      }),
      columnHelper.accessor("functionType", {
        header: "Type",
        cell: (info) => {
          const ft = info.getValue();
          const colors: Record<string, string> = {
            identity: "bg-green-100 text-green-800",
            unit_conversion: "bg-blue-100 text-blue-800",
            type_conversion: "bg-purple-100 text-purple-800",
            scaling: "bg-yellow-100 text-yellow-800",
            unknown: "bg-gray-100 text-gray-800",
          };
          return (
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[ft ?? "unknown"] ?? colors.unknown}`}>
              {ft ?? "unknown"}
            </span>
          );
        },
      }),
      columnHelper.accessor("inputType", {
        header: "Input → Output",
        cell: (info) => (
          <span className="font-mono text-xs">
            {info.getValue() ?? "?"} → {info.row.original.outputType ?? "?"}
          </span>
        ),
        enableSorting: false,
        enableColumnFilter: false,
      }),
      columnHelper.accessor("confidence", {
        header: "Confidence",
        cell: (info) => {
          const c = info.getValue();
          return c != null ? `${(c * 100).toFixed(0)}%` : "—";
        },
      }),
    ],
    [],
  );

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Transforms</h1>

      <div className="flex flex-wrap gap-3 mb-6">
        <select
          className="border rounded px-3 py-2 text-sm"
          value={functionType ?? ""}
          onChange={(e) => setFunctionType(e.target.value || undefined)}
        >
          <option value="">All types</option>
          <option value="identity">Identity</option>
          <option value="unit_conversion">Unit Conversion</option>
          <option value="type_conversion">Type Conversion</option>
          <option value="scaling">Scaling</option>
          <option value="value_mapping">Value Mapping</option>
          <option value="unknown">Unknown</option>
        </select>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-4 mb-6">
          <p className="text-red-800">Unable to load transforms: {error.message}</p>
        </div>
      )}

      <EntityDataGrid
        columns={columns}
        data={transforms}
        isLoading={loading}
        totalCount={totalCount}
        hasNextPage={pageInfo?.hasNextPage}
        onLoadMore={() =>
          fetchMore({ variables: { after: pageInfo?.endCursor } })
        }
      />
    </div>
  );
}
