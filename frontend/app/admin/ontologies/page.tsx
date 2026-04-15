"use client";

import { useQuery } from "@apollo/client/react";
import { gql } from "@apollo/client";
import { ONTOLOGY_SOURCES } from "@/graphql/queries";

const ONTOLOGY_STORE_INFO = gql`
  query OntologyStoreInfo {
    ontologyStoreInfo {
      name
      displayName
      termCount
      format
      checksum
      lastRefreshed
    }
  }
`;

interface OntologySourceNode {
  id: string;
  name: string;
  displayName: string;
  url: string;
  format: string;
  termCount: number;
  active: boolean;
  lastRefreshedAt?: string;
  createdAt: string;
}

interface StoreEntry {
  name: string;
  displayName: string;
  termCount: number;
  format: string;
  checksum: string;
  lastRefreshed: string;
}

export default function OntologyAdminPage() {
  const { data, loading, error } = useQuery<{ ontologySources: OntologySourceNode[] }>(ONTOLOGY_SOURCES);
  const { data: storeData } = useQuery<{ ontologyStoreInfo: StoreEntry[] }>(ONTOLOGY_STORE_INFO);

  const sources = data?.ontologySources ?? [];
  const storeEntries = storeData?.ontologyStoreInfo ?? [];

  return (
    <div>
      <h1 className="text-xl font-bold mb-4">Ontology Sources</h1>

      {/* Pyoxigraph Store — live loaded ontologies */}
      {storeEntries.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-2">Loaded in Ontology Store (pyoxigraph)</h2>
          <div className="border rounded overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-blue-50 border-b">
                  <th className="text-left px-3 py-2 font-medium">Name</th>
                  <th className="text-left px-3 py-2 font-medium">Terms</th>
                  <th className="text-left px-3 py-2 font-medium">Format</th>
                  <th className="text-left px-3 py-2 font-medium">Checksum</th>
                </tr>
              </thead>
              <tbody>
                {storeEntries.map((e) => (
                  <tr key={e.name} className="border-b hover:bg-gray-50">
                    <td className="px-3 py-2 font-medium">{e.displayName || e.name}</td>
                    <td className="px-3 py-2 font-mono">{e.termCount.toLocaleString()}</td>
                    <td className="px-3 py-2 text-xs">{e.format}</td>
                    <td className="px-3 py-2 text-xs font-mono text-gray-400">{e.checksum?.slice(0, 12)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <h2 className="text-sm font-semibold text-gray-700 mb-2">Registered Sources (database)</h2>
      <p className="text-sm text-gray-500 mb-4">
        Manage ontology sources used for element enrichment. Add new ontologies via CLI:
        <code className="ml-1 bg-gray-100 px-1 rounded text-xs">undata-library ontology add --name NAME --url URL --format owl</code>
      </p>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-3 mb-4 text-sm text-red-800">
          {error.message}
        </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-10 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="border rounded overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b">
                <th className="text-left px-3 py-2 font-medium">Name</th>
                <th className="text-left px-3 py-2 font-medium">Terms</th>
                <th className="text-left px-3 py-2 font-medium">Format</th>
                <th className="text-left px-3 py-2 font-medium">Status</th>
                <th className="text-left px-3 py-2 font-medium">Last Refreshed</th>
                <th className="text-left px-3 py-2 font-medium">URL</th>
              </tr>
            </thead>
            <tbody>
              {sources.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-gray-500">
                    No ontology sources registered. Add sources via the CLI.
                  </td>
                </tr>
              ) : (
                sources.map((src) => (
                  <tr key={src.id} className="border-b hover:bg-gray-50">
                    <td className="px-3 py-2">
                      <div className="font-medium">{src.displayName || src.name}</div>
                      <div className="text-xs text-gray-400 font-mono">{src.name}</div>
                    </td>
                    <td className="px-3 py-2 font-mono">{src.termCount.toLocaleString()}</td>
                    <td className="px-3 py-2">
                      <span className="px-1.5 py-0.5 bg-gray-100 rounded text-xs">{src.format}</span>
                    </td>
                    <td className="px-3 py-2">
                      <span className={`px-1.5 py-0.5 rounded text-xs ${src.active ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"}`}>
                        {src.active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-500">
                      {src.lastRefreshedAt ? new Date(src.lastRefreshedAt).toLocaleDateString() : "—"}
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-400 truncate max-w-xs" title={src.url}>
                      {src.url}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
