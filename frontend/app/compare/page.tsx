import { ComparisonPage } from "@/components/ComparisonPage";
import { Suspense } from "react";

export default function ComparePage() {
  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Compare Elements</h1>
      <Suspense fallback={<div>Loading...</div>}>
        <ComparisonPage />
      </Suspense>
    </div>
  );
}
