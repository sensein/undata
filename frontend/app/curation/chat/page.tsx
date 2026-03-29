"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery, useMutation } from "@apollo/client/react";
import { gql } from "@apollo/client";
import { SplitPanel } from "@/components/SplitPanel";
import { ChatPanel } from "@/components/ChatPanel";
import { EntityDiff } from "@/components/EntityDiff";
import { GET_ELEMENT } from "@/graphql/queries";
import type { ChatEvent } from "@/lib/chat-api";
import type { ElementNode } from "@/graphql/types";

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
  const searchParams = useSearchParams();
  const entitySha = searchParams.get("entity");

  const { data } = useQuery<{ element: ElementNode | null }>(GET_ELEMENT, {
    variables: { sha256: entitySha || "" },
    skip: !entitySha,
  });

  const [pendingDiffs, setPendingDiffs] = useState<DiffEntry[]>([]);
  const [updateElement] = useMutation(UPDATE_ELEMENT);

  const entity = data?.element;
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
        <ChatPanel entityContext={entityContext} onToolResult={handleToolResult} />
      }
      rightContent={
        <div className="p-4">
          <h2 className="font-semibold mb-3">
            {entity
              ? `Editing: ${entity.provenance?.[0]?.name ?? entity.sha256.slice(0, 12)}`
              : "Select an entity to edit"}
          </h2>

          {entity && (
            <div className="mb-4 text-xs space-y-1">
              <div><span className="text-gray-500">Type:</span> {entity.dataType}</div>
              <div><span className="text-gray-500">Unit:</span> {entity.unit ?? "—"}</div>
              <div><span className="text-gray-500">Description:</span> {entity.description ?? "—"}</div>
              <div><span className="text-gray-500">SHA:</span> <span className="font-mono">{entity.sha256.slice(0, 20)}...</span></div>
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
