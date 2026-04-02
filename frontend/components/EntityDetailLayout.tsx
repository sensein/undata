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

function AnnotationChip({ a }: { a: OntologyAnnotation }) {
  // Build CURIE from ontology + label
  const curie = a.ontology ? `${a.ontology}:${a.termLabel}` : a.termLabel;
  const relationIcons: Record<string, string> = {
    "skos:exactMatch": "≡",
    "skos:closeMatch": "≈",
    "skos:broadMatch": "⊃",
    "skos:narrowMatch": "⊂",
    "skos:relatedMatch": "~",
  };
  const icon = relationIcons[a.mappingRelation] ?? "·";

  return (
    <a
      href={a.termUri}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-green-50 text-green-800 rounded text-xs hover:bg-green-100 transition-colors"
      title={`${a.mappingRelation} — ${a.termUri}`}
    >
      <span className="text-green-600">{icon}</span>
      <span>{curie}</span>
      <span className="text-green-500 text-[10px]">{a.mappingRelation?.replace("skos:", "")}</span>
      <span className="text-green-500 font-mono">{a.score?.toFixed(2)}</span>
      <span className="text-green-400 text-[10px]">↗</span>
    </a>
  );
}

function ProvenanceBadgeStrip({ provenance }: { provenance: ProvenanceEntry[] }) {
  const [expanded, setExpanded] = useState<number | null>(null);

  return (
    <div>
      <div className="flex flex-wrap gap-1.5 items-center">
        <span className="text-xs text-gray-500 mr-1">Sources:</span>
        {provenance.map((p, i) => (
          <button
            key={i}
            onClick={() => setExpanded(expanded === i ? null : i)}
            className="inline-flex items-center gap-1"
          >
            <SourceBadge source={p.source} />
            {p.className && <span className="text-[10px] text-gray-400">{p.className}</span>}
          </button>
        ))}
      </div>
      {expanded !== null && provenance[expanded] && (
        <div className="mt-1.5 border rounded p-2 text-xs bg-gray-50">
          <div className="flex gap-3">
            <div><span className="text-gray-500">Class:</span> {provenance[expanded].className || "—"}</div>
            <div><span className="text-gray-500">Name:</span> {provenance[expanded].name}</div>
          </div>
          {provenance[expanded].description && (
            <p className="text-gray-600 mt-1">{provenance[expanded].description}</p>
          )}
        </div>
      )}
    </div>
  );
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
  const { bg, text: textColor } = getEntityColor(entityType);

  const tabs: { key: Tab; label: string }[] = [
    { key: "summary", label: "Summary" },
    { key: "flags", label: "Flags" },
    { key: "activity", label: "Activity" },
  ];

  return (
    <div className="max-w-6xl">
      {/* Back link */}
      <Link href={backHref} className="text-xs text-gray-500 hover:text-gray-700 mb-2 block">
        ← {backLabel}
      </Link>

      {/* Identity block */}
      <div className="flex items-center gap-2 mb-1">
        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${bg} ${textColor} uppercase`}>
          {entityType}
        </span>
        <h1 className="text-xl font-bold font-mono">{title}</h1>
        {source && <SourceBadge source={source} />}
        {status && <StatusBadge status={status} />}
      </div>

      {description && <p className="text-gray-600 text-sm mb-2">{description}</p>}

      {/* SHA-256 + action buttons */}
      <div className="flex items-center justify-between mb-3">
        <div className="text-[10px] text-gray-400 font-mono break-all flex-1">{sha256}</div>
        <div className="flex gap-2 ml-4 flex-shrink-0">
          <a
            href={`/curation/chat?entity=${sha256}`}
            className="px-2 py-1 bg-blue-50 text-blue-700 border border-blue-200 rounded text-xs hover:bg-blue-100"
          >
            Suggest Change
          </a>
        </div>
      </div>

      {/* Tab navigation */}
      <div className="border-b mb-3">
        <div className="flex gap-4">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`pb-1.5 text-xs font-medium border-b-2 transition-colors ${
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
        <div className="space-y-3">
          {/* Custom content (semantic properties) */}
          {children}

          {/* Provenance — compact horizontal badge strip */}
          {provenance.length > 0 && (
            <div>
              <ProvenanceBadgeStrip provenance={provenance} />
            </div>
          )}

          {/* Ontology Annotations — compact chips */}
          {annotations.length > 0 && (
            <div id="annotations">
              <div className="text-xs text-gray-500 mb-1">Ontology ({annotations.length})</div>
              <div className="flex flex-wrap gap-1">
                {annotations.map((a, i) => (
                  <AnnotationChip key={i} a={a} />
                ))}
              </div>
            </div>
          )}

          {/* Related entities */}
          {relatedContent}
        </div>
      )}

      {activeTab === "flags" && (
        <div>{flagsContent ?? <p className="text-gray-500 text-sm">No flags for this entity.</p>}</div>
      )}

      {activeTab === "activity" && (
        <div>{activityContent ?? <p className="text-gray-500 text-sm">No activity for this entity.</p>}</div>
      )}
    </div>
  );
}
