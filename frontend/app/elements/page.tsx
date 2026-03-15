import { ElementsSearch } from "@/components/ElementsSearch";
import { Suspense } from "react";

export default function ElementsPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <ElementsSearch />
    </Suspense>
  );
}
