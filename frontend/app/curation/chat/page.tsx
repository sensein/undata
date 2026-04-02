"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery, useMutation } from "@apollo/client/react";
import { gql } from "@apollo/client";
import { SplitPanel } from "@/components/SplitPanel";
import { ChatPanel } from "@/components/ChatPanel";
import { EntityDiff } from "@/components/EntityDiff";
import { GET_ELEMENT, GET_SCHEMA, GET_VALUE, GET_VALUESET, FLAGS_FOR_ENTITY } from "@/graphql/queries";
import { EntityInlineDetail } from "@/components/EntityInlineDetail";
import { StatusBadge } from "@/components/StatusBadge";
import type { ChatEvent } from "@/lib/chat-api";
import type { CurationFlagConnection, CurationFlagNode, Edge } from "@/graphql/types";

const UPDATE_ELEMENT = gql`
  mutation UpdateElement($sha256: String!, $input: UpdateElementInput!) {
    updateElement(sha256: $sha256, input: $input) {
      sha256
      dataType
      unit
      description
    }
  }
`;

interface DiffEntry {
  field: string;
  old_value: unknown;
  new_value: unknown;
}

export default function CurationChatPage() {
  return (
    <Suspense fallback={<div className="p-8 text-gray-500">Loading curation chat...</div>}>
      <CurationChatContent />
    </Suspense>
  );
}

function CurationChatContent() {
  const searchParams = useSearchParams();
  const entitySha = searchParams.get("entity");
  const entityType = searchParams.get("type") || "element";

  // Query the appropriate entity type
  const ENTITY_QUERIES: Record<string, { query: typeof GET_ELEMENT; key: string }> = {
    element: { query: GET_ELEMENT, key: "element" },
    schema: { query: GET_SCHEMA, key: "schema_" },
    value: { query: GET_VALUE, key: "value" },
    valueset: { query: GET_VALUESET, key: "valueset" },
  };
  const entityQuery = ENTITY_QUERIES[entityType] ?? ENTITY_QUERIES.element;

  const { data } = useQuery(entityQuery.query, {
    variables: { sha256: entitySha || "" },
    skip: !entitySha,
  });

  // Load flags for this entity
  const { data: flagsData } = useQuery<{ flagsForEntity: CurationFlagConnection }>(FLAGS_FOR_ENTITY, {
    variables: { entityType, entityRef: entitySha || "" },
    skip: !entitySha,
  });

  const [pendingDiffs, setPendingDiffs] = useState<DiffEntry[]>([]);
  const [updateElement] = useMutation(UPDATE_ELEMENT);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const entity = (data as any)?.[entityQuery.key];
  const flags = (flagsData?.flagsForEntity?.edges ?? []) as Edge<CurationFlagNode>[];
  const entityContext = entity
    ? { sha256: entity.sha256, semantic: entity.semantic, provenance: entity.provenance }
    : undefined;

  const handleToolResult = (event: ChatEvent) => {
    if (event.name === "propose_entity_change" && event.result) {
      const diff = event.result.diff as DiffEntry | undefined;
      if (diff) {
        setPendingDiffs((prev) => [...prev, diff]);
      }
    }
  };

  const handleApply = async (diff: DiffEntry) => {
    if (!entitySha) return;
    try {
      await updateElement({
        variables: {
          sha256: entitySha,
          input: { [diff.field]: diff.new_value, reason: `Changed ${diff.field}` },
        },
      });
      setPendingDiffs((prev) => prev.filter((d) => d !== diff));
    } catch (e) {
      alert(`Error: ${e}`);
    }
  };

  const handleApplyAll = async () => {
    for (const diff of pendingDiffs) {
      await handleApply(diff);
    }
  };

  const handleDiscard = (diff: DiffEntry) => {
    setPendingDiffs((prev) => prev.filter((d) => d !== diff));
  };

  return (
    <SplitPanel
      leftLabel="Chat"
      rightLabel="Changes"
      leftContent={
        <ChatPanel entityContext={entityContext} onToolResult={handleToolResult} autoSuggest={!!entitySha} />
      }
      rightContent={
        <div className="p-4">
          <h2 className="font-semibold mb-3">
            {entity
              ? `Editing: ${entity.provenance?.[0]?.name ?? entity.sha256?.slice(0, 12)}`
              : entitySha
                ? "Loading entity..."
                : "Start a conversation or select an entity to edit"}
          </h2>

          {/* Full entity details — same as curation queue detail panel */}
          {entitySha && (
            <div className="mb-4 space-y-2">
              <div className="flex gap-2 text-xs">
                <a
                  href={`/${entityType === "element" ? "elements" : entityType === "schema" ? "schemas" : entityType === "value" ? "values" : entityType === "valueset" ? "valuesets" : "elements"}/${entitySha}`}
                  className="text-blue-600 hover:underline"
                >
                  View full detail page ↗
                </a>
              </div>
              <EntityInlineDetail entityType={entityType} entityRef={entitySha} />

              {/* Curation flags for this entity */}
              {flags.length > 0 && (
                <div className="mt-2">
                  <div className="text-xs text-gray-500 mb-1">Curation Flags ({flags.length})</div>
                  <div className="space-y-1">
                    {flags.map((e) => {
                      const f = e.node;
                      return (
                        <div key={f.id} className="flex items-center gap-2 text-xs bg-white border rounded p-1.5">
                          <StatusBadge status={f.status} />
                          <span className="px-1.5 py-0.5 bg-yellow-100 text-yellow-800 rounded text-[10px]">
                            {f.flagType.replace(/_/g, " ")}
                          </span>
                          <span className="text-gray-500 truncate">
                            {String((f.context as Record<string, unknown>)?.reason ?? "")}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          <EntityDiff
            diffs={pendingDiffs}
            onApply={handleApply}
            onDiscard={handleDiscard}
            onApplyAll={pendingDiffs.length > 0 ? handleApplyAll : undefined}
            onDiscardAll={pendingDiffs.length > 0 ? () => setPendingDiffs([]) : undefined}
          />
        </div>
      }
    />
  );
}
