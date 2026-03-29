"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@apollo/client/react";
import { createColumnHelper } from "@tanstack/react-table";
import { BROWSE_ELEMENTS, BROWSE_SCHEMAS, BROWSE_VALUES, BROWSE_VALUESETS } from "@/graphql/queries";
import { EntityDataGrid } from "@/components/EntityDataGrid";
import { EntityTag } from "@/components/EntityTag";
import { SourceBadge } from "@/components/SourceBadge";
import type {
  ElementConnection,
  SchemaConnection,
  ValueConnection,
  Connection,
  ElementNode,
  SchemaNode,
  ValueNode,
  ValueSetNode,
  Edge,
  OntologyAnnotation,
} from "@/graphql/types";

type Tab = "elements" | "schemas" | "values" | "valuesets";

const TABS: { key: Tab; label: string }[] = [
  { key: "elements", label: "Elements" },
  { key: "schemas", label: "Schemas" },
  { key: "values", label: "Values" },
  { key: "valuesets", label: "Valuesets" },
];

const elementColumnHelper = createColumnHelper<ElementNode>();
const schemaColumnHelper = createColumnHelper<SchemaNode>();
const valueColumnHelper = createColumnHelper<ValueNode>();
const valuesetColumnHelper = createColumnHelper<ValueSetNode>();

export default function SourceDetailPage() {
  const params = useParams();
  const source = params.name as string;
  const [activeTab, setActiveTab] = useState<Tab>("elements");

  // Queries for all entity types (always fetch first page for counts)
  const elemQuery = useQuery<{ browseElements: ElementConnection }>(
    BROWSE_ELEMENTS,
    { variables: { source, first: 50 } },
  );
  const schemaQuery = useQuery<{ browseSchemas: SchemaConnection }>(
    BROWSE_SCHEMAS,
    { variables: { source, first: 50 } },
  );
  const valueQuery = useQuery<{ browseValues: ValueConnection }>(
    BROWSE_VALUES,
    { variables: { source, first: 50 } },
  );
  const valuesetQuery = useQuery<{ browseValuesets: Connection<ValueSetNode> }>(
    BROWSE_VALUESETS,
    { variables: { source, first: 50 } },
  );

  const counts = {
    elements: elemQuery.data?.browseElements?.totalCount ?? 0,
    schemas: schemaQuery.data?.browseSchemas?.totalCount ?? 0,
    values: valueQuery.data?.browseValues?.totalCount ?? 0,
    valuesets: valuesetQuery.data?.browseValuesets?.totalCount ?? 0,
  };

  // Element columns
  const elementColumns = useMemo(
    () => [
      elementColumnHelper.accessor("sha256", {
        header: "Name",
        cell: (info) => {
          const prov = info.row.original.provenance?.[0];
          return (
            <EntityTag
              entityType="elements"
              sha256={info.getValue()}
              label={prov?.name ?? info.row.original.fileName ?? info.getValue().slice(0, 12)}
            />
          );
        },
        sortingFn: (rowA, rowB) => {
          const nameA = (rowA.original.provenance?.[0]?.name ?? rowA.original.fileName ?? "").toLowerCase();
          const nameB = (rowB.original.provenance?.[0]?.name ?? rowB.original.fileName ?? "").toLowerCase();
          return nameA.localeCompare(nameB);
        },
        enableColumnFilter: false,
      }),
      elementColumnHelper.accessor("dataType", {
        header: "Type",
        cell: (info) => <span className="font-mono text-sm">{info.getValue() ?? "\u2014"}</span>,
      }),
      elementColumnHelper.display({
        id: "annotations",
        header: "Ontology",
        cell: (info) => {
          const anns = info.row.original.ontologyAnnotations ?? [];
          const primary = anns.find((a: OntologyAnnotation) => a.primary);
          if (!primary) return <span className="text-gray-400">{"\u2014"}</span>;
          return (
            <span className="text-green-700 text-sm">
              {primary.termLabel} ({primary.score?.toFixed(2)})
            </span>
          );
        },
        enableSorting: false,
        enableColumnFilter: false,
      }),
      elementColumnHelper.accessor("description", {
        header: "Description",
        cell: (info) => (
          <span className="text-gray-600 text-sm truncate block max-w-xs">
            {info.getValue() ?? info.row.original.provenance?.[0]?.description ?? "\u2014"}
          </span>
        ),
        enableSorting: false,
      }),
    ],
    [],
  );

  // Schema columns
  const schemaColumns = useMemo(
    () => [
      schemaColumnHelper.accessor("sha256", {
        header: "Name",
        cell: (info) => {
          const prov = info.row.original.provenance?.[0];
          return (
            <EntityTag
              entityType="schemas"
              sha256={info.getValue()}
              label={prov?.name ?? info.getValue().slice(0, 12)}
            />
          );
        },
        enableColumnFilter: false,
      }),
      schemaColumnHelper.accessor("subclassOf", {
        header: "Subclass Of",
        cell: (info) => <span className="font-mono text-sm">{info.getValue() ?? "\u2014"}</span>,
      }),
      schemaColumnHelper.display({
        id: "properties",
        header: "Properties",
        cell: (info) => (
          <span className="text-sm text-gray-600">
            {info.row.original.properties?.length ?? 0}
          </span>
        ),
        enableSorting: false,
        enableColumnFilter: false,
      }),
      schemaColumnHelper.accessor("description", {
        header: "Description",
        cell: (info) => (
          <span className="text-gray-600 text-sm truncate block max-w-xs">
            {info.getValue() ?? "\u2014"}
          </span>
        ),
        enableSorting: false,
      }),
    ],
    [],
  );

  // Value columns
  const valueColumns = useMemo(
    () => [
      valueColumnHelper.accessor("sha256", {
        header: "Label",
        cell: (info) => {
          const label = info.row.original.label ?? info.row.original.provenance?.[0]?.name ?? info.getValue().slice(0, 12);
          return (
            <EntityTag
              entityType="values"
              sha256={info.getValue()}
              label={label}
            />
          );
        },
        enableColumnFilter: false,
      }),
      valueColumnHelper.accessor("valueType", {
        header: "Value Type",
        cell: (info) => <span className="font-mono text-sm">{info.getValue() ?? "\u2014"}</span>,
      }),
      valueColumnHelper.display({
        id: "annotations",
        header: "Ontology",
        cell: (info) => {
          const anns = info.row.original.ontologyAnnotations ?? [];
          const primary = anns.find((a: OntologyAnnotation) => a.primary);
          if (!primary) return <span className="text-gray-400">{"\u2014"}</span>;
          return (
            <span className="text-green-700 text-sm">
              {primary.termLabel} ({primary.score?.toFixed(2)})
            </span>
          );
        },
        enableSorting: false,
        enableColumnFilter: false,
      }),
      valueColumnHelper.accessor("description", {
        header: "Description",
        cell: (info) => (
          <span className="text-gray-600 text-sm truncate block max-w-xs">
            {info.getValue() ?? "\u2014"}
          </span>
        ),
        enableSorting: false,
      }),
    ],
    [],
  );

  // Valueset columns
  const valuesetColumns = useMemo(
    () => [
      valuesetColumnHelper.accessor("sha256", {
        header: "Name",
        cell: (info) => {
          const name = info.row.original.name ?? info.row.original.provenance?.[0]?.name ?? info.getValue().slice(0, 12);
          return (
            <EntityTag
              entityType="valuesets"
              sha256={info.getValue()}
              label={name}
            />
          );
        },
        enableColumnFilter: false,
      }),
      valuesetColumnHelper.display({
        id: "members",
        header: "Members",
        cell: (info) => (
          <span className="text-sm text-gray-600">
            {info.row.original.members?.length ?? 0}
          </span>
        ),
        enableSorting: false,
        enableColumnFilter: false,
      }),
      valuesetColumnHelper.accessor("description", {
        header: "Description",
        cell: (info) => (
          <span className="text-gray-600 text-sm truncate block max-w-xs">
            {info.getValue() ?? "\u2014"}
          </span>
        ),
        enableSorting: false,
      }),
    ],
    [],
  );

  // Active tab data
  const elements = useMemo(
    () => (elemQuery.data?.browseElements?.edges ?? []).map((e: Edge<ElementNode>) => e.node),
    [elemQuery.data],
  );
  const schemas = useMemo(
    () => (schemaQuery.data?.browseSchemas?.edges ?? []).map((e: Edge<SchemaNode>) => e.node),
    [schemaQuery.data],
  );
  const values = useMemo(
    () => (valueQuery.data?.browseValues?.edges ?? []).map((e: Edge<ValueNode>) => e.node),
    [valueQuery.data],
  );
  const valuesets = useMemo(
    () => (valuesetQuery.data?.browseValuesets?.edges ?? []).map((e: Edge<ValueSetNode>) => e.node),
    [valuesetQuery.data],
  );

  const anyLoading = elemQuery.loading || schemaQuery.loading || valueQuery.loading || valuesetQuery.loading;
  const anyError = elemQuery.error || schemaQuery.error || valueQuery.error || valuesetQuery.error;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <h1 className="text-2xl font-bold">Source:</h1>
        <SourceBadge source={source} />
      </div>

      {/* Counts */}
      <div className="flex flex-wrap gap-4 mb-6 text-sm text-gray-600">
        <span>{counts.elements} elements</span>
        <span>{counts.schemas} schemas</span>
        <span>{counts.values} values</span>
        <span>{counts.valuesets} valuesets</span>
      </div>

      {/* Error */}
      {anyError && (
        <div className="bg-red-50 border border-red-200 rounded p-4 mb-6">
          <p className="text-red-800">Unable to load data: {anyError.message}</p>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b mb-4">
        <div className="flex gap-0">
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === key
                  ? "border-blue-500 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }`}
              onClick={() => setActiveTab(key)}
            >
              {label} ({counts[key]})
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      {activeTab === "elements" && (
        <EntityDataGrid
          columns={elementColumns}
          data={elements}
          isLoading={anyLoading}
          totalCount={counts.elements}
          hasNextPage={elemQuery.data?.browseElements?.pageInfo?.hasNextPage}
          onLoadMore={() =>
            elemQuery.fetchMore({
              variables: { after: elemQuery.data?.browseElements?.pageInfo?.endCursor },
            })
          }
        />
      )}

      {activeTab === "schemas" && (
        <EntityDataGrid
          columns={schemaColumns}
          data={schemas}
          isLoading={anyLoading}
          totalCount={counts.schemas}
          hasNextPage={schemaQuery.data?.browseSchemas?.pageInfo?.hasNextPage}
          onLoadMore={() =>
            schemaQuery.fetchMore({
              variables: { after: schemaQuery.data?.browseSchemas?.pageInfo?.endCursor },
            })
          }
        />
      )}

      {activeTab === "values" && (
        <EntityDataGrid
          columns={valueColumns}
          data={values}
          isLoading={anyLoading}
          totalCount={counts.values}
          hasNextPage={valueQuery.data?.browseValues?.pageInfo?.hasNextPage}
          onLoadMore={() =>
            valueQuery.fetchMore({
              variables: { after: valueQuery.data?.browseValues?.pageInfo?.endCursor },
            })
          }
        />
      )}

      {activeTab === "valuesets" && (
        <EntityDataGrid
          columns={valuesetColumns}
          data={valuesets}
          isLoading={anyLoading}
          totalCount={counts.valuesets}
          hasNextPage={valuesetQuery.data?.browseValuesets?.pageInfo?.hasNextPage}
          onLoadMore={() =>
            valuesetQuery.fetchMore({
              variables: { after: valuesetQuery.data?.browseValuesets?.pageInfo?.endCursor },
            })
          }
        />
      )}
    </div>
  );
}
