"use client";

import Link from "next/link";
import { useState } from "react";
import { SourceBadge } from "./SourceBadge";
import { StatusBadge } from "./StatusBadge";
import { getEntityColor } from "@/lib/source-colors";
import type { ProvenanceEntry, OntologyAnnotation } from "@/graphql/types";

type Tab = "summary" | "flags" | "activity";

interface EntityDetailLayoutProps {
  entityType: string;
  backHref: string;
  backLabel: string;
  title: string;
  source?: string;
  sha256: string;
  description?: string;
  status?: string;
  provenance?: ProvenanceEntry[];
  annotations?: OntologyAnnotation[];
  children: React.ReactNode; // Summary tab content
  flagsContent?: React.ReactNode;
  activityContent?: React.ReactNode;
  relatedContent?: React.ReactNode;
}

export function EntityDetailLayout({
  entityType,
  backHref,
  backLabel,
  title,
  source,
  sha256,
  description,
  status,
  provenance = [],
  annotations = [],
  children,
  flagsContent,
  activityContent,
  relatedContent,
}: EntityDetailLayoutProps) {
  const [activeTab, setActiveTab] = useState<Tab>("summary");
  const { bg, text } = getEntityColor(entityType);

  const tabs: { key: Tab; label: string }[] = [
    { key: "summary", label: "Summary" },
    { key: "flags", label: "Flags" },
    { key: "activity", label: "Activity" },
  ];

  return (
    <div className="max-w-5xl">
      {/* Back link */}
      <Link href={backHref} className="text-sm text-gray-500 hover:text-gray-700 mb-4 block">
        ← {backLabel}
      </Link>

      {/* Identity block */}
      <div className="flex items-center gap-3 mb-2">
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${bg} ${text} uppercase`}>
          {entityType}
        </span>
        <h1 className="text-2xl font-bold font-mono">{title}</h1>
        {source && <SourceBadge source={source} />}
        {status && <StatusBadge status={status} />}
      </div>

      {description && <p className="text-gray-600 mb-4">{description}</p>}

      {/* SHA-256 */}
      <div className="text-xs text-gray-400 font-mono mb-6 break-all">{sha256}</div>

      {/* Tab navigation */}
      <div className="border-b mb-6">
        <div className="flex gap-6">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`pb-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? "border-blue-500 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      {activeTab === "summary" && (
        <div>
          {/* Custom content (semantic properties) */}
          {children}

          {/* Provenance */}
          {provenance.length > 0 && (
            <div className="mt-6">
              <h2 className="text-lg font-semibold mb-3">Provenance ({provenance.length})</h2>
              <div className="space-y-2">
                {provenance.map((p, i) => (
                  <div key={i} className="border rounded p-3 text-sm">
                    <div className="flex gap-4">
                      <div><span className="text-gray-500">Source:</span> <SourceBadge source={p.source} /></div>
                      {p.className && <div><span className="text-gray-500">Class:</span> {p.className}</div>}
                      <div><span className="text-gray-500">Name:</span> {p.name}</div>
                    </div>
                    {p.description && <div className="text-gray-600 mt-1">{p.description}</div>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Ontology Annotations */}
          {annotations.length > 0 && (
            <div className="mt-6" id="annotations">
              <h2 className="text-lg font-semibold mb-3">Ontology Annotations ({annotations.length})</h2>
              <div className="space-y-2">
                {annotations.map((a, i) => (
                  <div key={i} className="border rounded p-3 flex justify-between items-center">
                    <div>
                      <span className="font-medium">{a.termLabel || a.termUri}</span>
                      <span className="text-gray-400 ml-2 text-xs">{a.ontology}</span>
                      <span className="text-gray-400 ml-2 text-xs">{a.mappingRelation}</span>
                    </div>
                    <span className="text-sm font-mono">{a.score?.toFixed(3)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Related entities */}
          {relatedContent}
        </div>
      )}

      {activeTab === "flags" && (
        <div>{flagsContent ?? <p className="text-gray-500">No flags for this entity.</p>}</div>
      )}

      {activeTab === "activity" && (
        <div>{activityContent ?? <p className="text-gray-500">No activity for this entity.</p>}</div>
      )}
    </div>
  );
}
