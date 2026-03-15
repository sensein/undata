"use client";

import { Input } from "@/components/ui/input";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function Home() {
  const [query, setQuery] = useState("");
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = query.trim();
    if (trimmed) {
      router.push(`/elements?q=${encodeURIComponent(trimmed)}`);
    }
  }

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight">
          undata Schema Explorer
        </h1>
        <p className="mt-3 text-lg text-muted-foreground">
          Search and browse neuroscience data elements across schemas
        </p>
      </div>
      <form onSubmit={handleSubmit} className="w-full max-w-lg">
        <Input
          type="search"
          placeholder='Search elements (e.g. "subject age", "electrode impedance")'
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="h-12 text-base"
          autoFocus
        />
      </form>
    </div>
  );
}
