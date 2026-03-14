"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { createElement } from "@/lib/api/elements";
import { getElements } from "@/lib/api/elements";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { getSources } from "@/lib/api/sources";
import { ErrorBanner } from "@/components/ErrorBanner";
import Link from "next/link";

interface FormData {
  name: string;
  data_type: string;
  description: string;
  required: boolean;
  multivalued: boolean;
  source_id: string;
  allowed_values: string;
}

const DATA_TYPES = ["string", "number", "boolean", "object", "array"];
const NAME_PATTERN = /^[a-zA-Z_][a-zA-Z0-9_ ]*$/;

export function AddElementForm() {
  const router = useRouter();
  const [form, setForm] = useState<FormData>({
    name: "",
    data_type: "string",
    description: "",
    required: false,
    multivalued: false,
    source_id: "",
    allowed_values: "",
  });
  const [errors, setErrors] = useState<Partial<Record<keyof FormData, string>>>(
    {},
  );
  const [nameBlurred, setNameBlurred] = useState(false);

  const { data: sources } = useQuery({
    queryKey: ["sources"],
    queryFn: getSources,
  });

  // Duplicate check on name blur
  const { data: duplicates } = useQuery({
    queryKey: ["duplicate-check", form.name],
    queryFn: () => getElements({ q: form.name, limit: 5 }),
    enabled: nameBlurred && form.name.length >= 2,
  });

  const exactMatches =
    duplicates?.items.filter(
      (el) => el.name.toLowerCase() === form.name.toLowerCase(),
    ) || [];

  const mutation = useMutation({
    mutationFn: (payload: Parameters<typeof createElement>[0]) =>
      createElement(payload),
    onSuccess: (data) => {
      router.push(`/elements/${data.id}`);
    },
  });

  const validate = useCallback((): boolean => {
    const errs: Partial<Record<keyof FormData, string>> = {};

    if (!form.name.trim()) {
      errs.name = "Name is required";
    } else if (form.name.length > 200) {
      errs.name = "Name must be 200 characters or fewer";
    } else if (!NAME_PATTERN.test(form.name)) {
      errs.name =
        "Name must start with a letter or underscore and contain only letters, digits, underscores, or spaces";
    }

    if (!form.data_type) errs.data_type = "Data type is required";

    if (!form.description.trim()) {
      errs.description = "Description is required";
    } else if (form.description.length < 10) {
      errs.description = "Description must be at least 10 characters";
    } else if (form.description.length > 2000) {
      errs.description = "Description must be 2000 characters or fewer";
    }

    if (!form.source_id) errs.source_id = "Source is required";

    setErrors(errs);
    return Object.keys(errs).length === 0;
  }, [form]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    const allowed = form.allowed_values
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean);

    mutation.mutate({
      name: form.name.trim(),
      data_type: form.data_type,
      description: form.description.trim(),
      required: form.required,
      multivalued: form.multivalued,
      source_id: form.source_id,
      allowed_values: allowed.length > 0 ? allowed : undefined,
    });
  }

  function update(field: keyof FormData, value: string | boolean) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-xl space-y-6">
      {mutation.error && <ErrorBanner error={mutation.error as Error} />}

      <div>
        <Label htmlFor="name">Name *</Label>
        <Input
          id="name"
          value={form.name}
          onChange={(e) => update("name", e.target.value)}
          onBlur={() => setNameBlurred(true)}
          placeholder="e.g. subject_age"
          aria-invalid={!!errors.name}
        />
        {errors.name && (
          <p className="mt-1 text-sm text-red-600">{errors.name}</p>
        )}
        {exactMatches.length > 0 && (
          <div className="mt-2 rounded border border-amber-200 bg-amber-50 p-3 text-sm">
            <p className="font-medium text-amber-800">
              Potential duplicate found:
            </p>
            <ul className="mt-1 space-y-1">
              {exactMatches.map((el) => (
                <li key={el.id}>
                  <Link
                    href={`/elements/${el.id}`}
                    className="text-blue-600 hover:underline"
                  >
                    {el.name}
                  </Link>{" "}
                  <span className="text-muted-foreground">
                    ({el.source.name})
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div>
        <Label htmlFor="data_type">Data Type *</Label>
        <select
          id="data_type"
          className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
          value={form.data_type}
          onChange={(e) => update("data_type", e.target.value)}
          aria-invalid={!!errors.data_type}
        >
          {DATA_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        {errors.data_type && (
          <p className="mt-1 text-sm text-red-600">{errors.data_type}</p>
        )}
      </div>

      <div>
        <Label htmlFor="description">Description *</Label>
        <Textarea
          id="description"
          value={form.description}
          onChange={(e) => update("description", e.target.value)}
          placeholder="Describe the data element (min 10 chars)"
          rows={3}
          aria-invalid={!!errors.description}
        />
        {errors.description && (
          <p className="mt-1 text-sm text-red-600">{errors.description}</p>
        )}
      </div>

      <div>
        <Label htmlFor="source_id">Source *</Label>
        <select
          id="source_id"
          className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
          value={form.source_id}
          onChange={(e) => update("source_id", e.target.value)}
          aria-invalid={!!errors.source_id}
        >
          <option value="">Select a source...</option>
          {sources?.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        {errors.source_id && (
          <p className="mt-1 text-sm text-red-600">{errors.source_id}</p>
        )}
      </div>

      <div className="flex gap-6">
        <div className="flex items-center gap-2">
          <input
            id="required"
            type="checkbox"
            checked={form.required}
            onChange={(e) => update("required", e.target.checked)}
          />
          <Label htmlFor="required">Required</Label>
        </div>
        <div className="flex items-center gap-2">
          <input
            id="multivalued"
            type="checkbox"
            checked={form.multivalued}
            onChange={(e) => update("multivalued", e.target.checked)}
          />
          <Label htmlFor="multivalued">Multivalued</Label>
        </div>
      </div>

      <div>
        <Label htmlFor="allowed_values">Allowed Values (comma-separated)</Label>
        <Input
          id="allowed_values"
          value={form.allowed_values}
          onChange={(e) => update("allowed_values", e.target.value)}
          placeholder="e.g. male, female, other"
        />
      </div>

      <Button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Creating..." : "Create Element"}
      </Button>
    </form>
  );
}
