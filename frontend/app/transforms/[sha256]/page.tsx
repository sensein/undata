"use client";

import { useQuery } from "@apollo/client/react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { GET_TRANSFORM } from "@/graphql/queries";
import { EntityTag } from "@/components/EntityTag";
import { SourceBadge } from "@/components/SourceBadge";
import type { TransformNode } from "@/graphql/types";

export default function TransformDetailPage() {
  const params = useParams();
  const sha256 = params.sha256 as string;

  const { data, loading, error } = useQuery<{ transform: TransformNode | null }>(GET_TRANSFORM, {
    variables: { sha256 },
  });

  if (loading) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-16 bg-gray-100 rounded animate-pulse" />
        ))}
      </div>
    );
  }

  if (error || !data?.transform) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 text-lg">{error ? `Error: ${error.message}` : "Transform not found"}</p>
      </div>
    );
  }

  const t = data.transform;
  const prov = t.provenance?.[0];

  // Extract element names from URIs
  function parseRef(val: string) {
    const slug = val.includes("/") ? val.split("/").pop()! : val;
    const lastU = slug.lastIndexOf("_");
    if (lastU > 0) return { name: slug.substring(0, lastU), sha: slug.substring(lastU + 1) };
    return { name: slug, sha: slug.slice(0, 12) };
  }
  const src = parseRef(t.sourceElement);
  const tgt = parseRef(t.targetElement);
  const srcName = src.name;
  const tgtName = tgt.name;
  const srcSha = src.sha;
  const tgtSha = tgt.sha;

  const functionColors: Record<string, string> = {
    identity: "bg-green-100 text-green-800",
    unit_conversion: "bg-blue-100 text-blue-800",
    type_conversion: "bg-purple-100 text-purple-800",
    scaling: "bg-yellow-100 text-yellow-800",
    unknown: "bg-gray-100 text-gray-800",
  };

  return (
    <div>
      <Link href="/transforms" className="text-sm text-blue-600 hover:underline mb-4 block">
        &larr; Back to transforms
      </Link>

      <div className="flex items-center justify-between mb-2">
        <h1 className="text-2xl font-bold">
          {srcName} → {tgtName}
        </h1>
        <a
          href={`/curation/chat?entity=${t.sha256}&type=transform`}
          className="px-2 py-1 bg-blue-50 text-blue-700 border border-blue-200 rounded text-xs hover:bg-blue-100"
        >
          Suggest Change
        </a>
      </div>

      {prov?.source && <SourceBadge source={prov.source} />}

      <div className="mt-4 font-mono text-xs text-gray-500">SHA: {t.sha256}</div>

      {/* Transform Mapping */}
      <div className="mt-6 border rounded-lg p-6 bg-white">
        <h3 className="text-md font-semibold mb-4">Mapping</h3>
        <div className="flex items-center gap-4 flex-wrap">
          <div className="border rounded p-4 flex-1 min-w-[200px]">
            <div className="text-xs text-gray-500 uppercase mb-1">Source</div>
            <EntityTag entityType="elements" sha256={srcSha} label={srcName} />
            {t.inputType && (
              <div className="mt-2 text-xs text-gray-500">Type: <span className="font-mono">{t.inputType}</span></div>
            )}
          </div>

          <div className="text-2xl text-gray-400">→</div>

          <div className="border rounded p-4 flex-1 min-w-[200px]">
            <div className="text-xs text-gray-500 uppercase mb-1">Target</div>
            <EntityTag entityType="elements" sha256={tgtSha} label={tgtName} />
            {t.outputType && (
              <div className="mt-2 text-xs text-gray-500">Type: <span className="font-mono">{t.outputType}</span></div>
            )}
          </div>
        </div>
      </div>

      {/* Function Details */}
      <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="border rounded p-3">
          <div className="text-xs text-gray-500 uppercase">Function Type</div>
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${functionColors[t.functionType ?? "unknown"] ?? functionColors.unknown}`}>
            {t.functionType ?? "unknown"}
          </span>
        </div>
        {t.confidence != null && (
          <div className="border rounded p-3">
            <div className="text-xs text-gray-500 uppercase">Confidence</div>
            <div>{(t.confidence * 100).toFixed(0)}%</div>
          </div>
        )}
        {t.expression && (
          <div className="border rounded p-3 col-span-2">
            <div className="text-xs text-gray-500 uppercase">Expression</div>
            <code className="text-sm">{t.expression}</code>
          </div>
        )}
      </div>

      {/* Description */}
      {t.description && (
        <div className="mt-6 border rounded p-4">
          <h3 className="text-md font-semibold mb-2">Description</h3>
          <p className="text-gray-700">{t.description}</p>
        </div>
      )}

      {/* Provenance */}
      {t.provenance?.length > 0 && (
        <div className="mt-6">
          <h3 className="text-md font-semibold mb-3">Provenance</h3>
          <div className="space-y-2">
            {t.provenance.map((p, i) => (
              <div key={i} className="border rounded p-3 text-sm">
                <SourceBadge source={p.source} />
                {p.name && <span className="ml-2 text-gray-700">{p.name}</span>}
                {p.description && <p className="text-gray-500 mt-1">{p.description}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
