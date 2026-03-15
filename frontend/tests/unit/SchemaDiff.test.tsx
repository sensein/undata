import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SchemaDiff } from "@/components/SchemaDiff";
import type { SchemaDiffResult } from "@/lib/types";

const baseDiff: SchemaDiffResult = {
  schema_a: { id: "s1", name: "BIDS v1.8" },
  schema_b: { id: "s2", name: "BIDS v2.0" },
  added: ["electrode_count"],
  removed: ["old_field"],
  modified: [
    { field: "subject_age", old_type: "string", new_type: "integer" },
  ],
};

describe("SchemaDiff", () => {
  afterEach(() => cleanup());

  it("renders schema names", () => {
    render(<SchemaDiff diff={baseDiff} />);
    expect(screen.getByText("BIDS v1.8")).toBeInTheDocument();
    expect(screen.getByText("BIDS v2.0")).toBeInTheDocument();
  });

  it("renders added fields", () => {
    render(<SchemaDiff diff={baseDiff} />);
    expect(screen.getByText("+ electrode_count")).toBeInTheDocument();
    expect(screen.getByText("Added (1)")).toBeInTheDocument();
  });

  it("renders removed fields", () => {
    render(<SchemaDiff diff={baseDiff} />);
    expect(screen.getByText("- old_field")).toBeInTheDocument();
    expect(screen.getByText("Removed (1)")).toBeInTheDocument();
  });

  it("renders modified fields with old and new types", () => {
    render(<SchemaDiff diff={baseDiff} />);
    expect(screen.getByText("subject_age")).toBeInTheDocument();
    expect(screen.getByText("string")).toBeInTheDocument();
    expect(screen.getByText("integer")).toBeInTheDocument();
    expect(screen.getByText("Modified (1)")).toBeInTheDocument();
  });

  it("shows identical message when no changes", () => {
    const empty: SchemaDiffResult = {
      ...baseDiff,
      added: [],
      removed: [],
      modified: [],
    };
    render(<SchemaDiff diff={empty} />);
    expect(screen.getByText("Schemas are identical.")).toBeInTheDocument();
  });

  it("has accessible labels for added/removed/modified", () => {
    render(<SchemaDiff diff={baseDiff} />);
    expect(screen.getByLabelText("added field")).toBeInTheDocument();
    expect(screen.getByLabelText("removed field")).toBeInTheDocument();
    expect(screen.getByLabelText("modified field")).toBeInTheDocument();
  });
});
