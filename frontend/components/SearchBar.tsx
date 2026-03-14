"use client";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import DOMPurify from "dompurify";
import { useCallback, useEffect, useRef, useState } from "react";

interface SearchBarProps {
  initialQuery?: string;
  onSearch: (query: string) => void;
}

const MAX_QUERY_LENGTH = 500;

export function SearchBar({ initialQuery = "", onSearch }: SearchBarProps) {
  const [value, setValue] = useState(initialQuery);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const debouncedSearch = useCallback(
    (q: string) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => onSearch(q), 300);
    },
    [onSearch],
  );

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const raw = DOMPurify.sanitize(e.target.value, { ALLOWED_TAGS: [] }).slice(
      0,
      MAX_QUERY_LENGTH,
    );
    setValue(raw);
    debouncedSearch(raw.trim());
  }

  function handleClear() {
    setValue("");
    onSearch("");
  }

  return (
    <div className="flex gap-2">
      <Input
        type="search"
        placeholder="Search elements..."
        value={value}
        onChange={handleChange}
        className="h-10"
        aria-label="Search elements"
      />
      {value && (
        <Button variant="ghost" size="sm" onClick={handleClear}>
          Clear
        </Button>
      )}
    </div>
  );
}
