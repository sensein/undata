"use client";

import { useQuery } from "@apollo/client/react";
import { gql } from "@apollo/client";

const RELEASES = gql`
  query Releases($releaseType: String) {
    releases(releaseType: $releaseType) {
      id
      version
      releaseType
      filePath
      fileSize
      entityCounts
      downloadCount
      createdAt
    }
  }
`;

interface Release {
  id: string;
  version: string;
  releaseType: string;
  filePath: string;
  fileSize: number;
  entityCounts: Record<string, number> | null;
  downloadCount: number;
  createdAt: string;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DownloadsPage() {
  const { data, loading } = useQuery<{ releases: Release[] }>(RELEASES);
  const releases = data?.releases ?? [];

  return (
    <div>
      <h1 className="text-xl font-bold mb-4">Downloads</h1>
      <p className="text-sm text-gray-500 mb-6">
        Registry exports are produced nightly. Download the latest archive to get all entities, schemas, values, and embeddings.
      </p>

      {loading && <p className="text-gray-500">Loading releases...</p>}

      {releases.length === 0 && !loading && (
        <p className="text-gray-500">No releases available yet.</p>
      )}

      <div className="space-y-3">
        {releases.map((r) => (
          <div key={r.id} className="border rounded-lg p-4 flex items-center justify-between hover:bg-gray-50">
            <div>
              <div className="font-medium text-sm">{r.version}</div>
              <div className="text-xs text-gray-500 space-x-3">
                <span className={`px-1.5 py-0.5 rounded ${r.releaseType === "versioned" ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-600"}`}>
                  {r.releaseType}
                </span>
                <span>{formatBytes(r.fileSize)}</span>
                <span>{new Date(r.createdAt).toLocaleDateString()}</span>
                {r.entityCounts && (
                  <span>
                    {Object.entries(r.entityCounts)
                      .map(([k, v]) => `${v} ${k}`)
                      .join(", ")}
                  </span>
                )}
              </div>
            </div>
            <a
              href={`/api/downloads/${r.filePath.split("/").pop()}`}
              className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
              download
            >
              Download
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}
