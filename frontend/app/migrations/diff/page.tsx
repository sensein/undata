import { SchemaDiffPage } from "@/components/SchemaDiffPage";
import { Suspense } from "react";

export default function DiffPage() {
  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Schema Diff</h1>
      <Suspense fallback={<div>Loading...</div>}>
        <SchemaDiffPage />
      </Suspense>
    </div>
  );
}
