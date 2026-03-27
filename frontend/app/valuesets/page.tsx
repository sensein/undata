"use client";

import Link from "next/link";

export default function ValueSetsPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Value Sets</h1>
      <div className="text-center py-12">
        <p className="text-gray-500 text-lg">Value sets browser coming soon</p>
        <p className="text-gray-400 text-sm mt-1">
          Value sets are named collections of values (e.g., sex_options = male + female).
          Browse individual values on the{" "}
          <Link href="/values" className="text-blue-600 underline">
            Values page
          </Link>
          .
        </p>
      </div>
    </div>
  );
}
