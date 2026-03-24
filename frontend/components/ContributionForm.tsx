"use client";

import { useState } from "react";

interface ContributionFormProps {
  entityType: string;
  entityRef: string;
  onSubmit?: (data: { type: string; content: string }) => void;
}

export function ContributionForm({
  entityType,
  entityRef,
  onSubmit,
}: ContributionFormProps) {
  const [type, setType] = useState("suggest_annotation");
  const [content, setContent] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit?.({ type, content });
    setContent("");
  };

  return (
    <form onSubmit={handleSubmit} className="border rounded p-4 space-y-3">
      <h3 className="font-semibold">Contribute</h3>
      <p className="text-xs text-gray-500">
        {entityType}: {entityRef}
      </p>
      <select
        className="w-full border rounded px-3 py-2 text-sm"
        value={type}
        onChange={(e) => setType(e.target.value)}
      >
        <option value="suggest_annotation">Suggest Ontology Annotation</option>
        <option value="comment">Comment</option>
        <option value="flag_issue">Flag Issue</option>
        <option value="suggest_edit">Suggest Edit</option>
      </select>
      <textarea
        className="w-full border rounded px-3 py-2 text-sm"
        rows={3}
        placeholder="Your contribution..."
        value={content}
        onChange={(e) => setContent(e.target.value)}
      />
      <button
        type="submit"
        className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
      >
        Submit
      </button>
    </form>
  );
}
