"use client";

export default function SchemasPage() {
  return (
    <div className="max-w-7xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Schemas</h1>

      <div className="bg-blue-50 border border-blue-200 rounded p-4 text-sm">
        <p className="font-medium">Schema browser</p>
        <p className="text-gray-600 mt-1">
          915 schemas across 5 sources — sidecar field groups, modality classes,
          tabular data definitions, controlled vocabulary types, and model classes.
        </p>
        <p className="text-gray-600 mt-1">
          Schema browsing with inheritance visualization (is_a, mixins) requires
          the browseSchemas GraphQL query. Coming soon.
        </p>
      </div>
    </div>
  );
}
