"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function Home() {
  const [query, setQuery] = useState("");
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = query.trim();
    if (trimmed) {
      router.push(`/search?q=${encodeURIComponent(trimmed)}`);
    }
  }

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight">undata</h1>
        <p className="mt-3 text-lg text-gray-500">
          Universal data element registry for neuroscience
        </p>
      </div>
      <form onSubmit={handleSubmit} className="w-full max-w-lg">
        <input
          type="search"
          placeholder='Search all entities (e.g. "age", "electrode", "probe")'
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full h-12 text-base border rounded-lg px-4 focus:outline-none focus:ring-2 focus:ring-blue-500"
          autoFocus
        />
      </form>
      <div className="flex gap-6 text-sm text-gray-400">
        <span>2191 elements</span>
        <span>915 schemas</span>
        <span>5542 values</span>
        <span>214 valuesets</span>
        <span>5 sources</span>
      </div>
    </div>
  );
}
