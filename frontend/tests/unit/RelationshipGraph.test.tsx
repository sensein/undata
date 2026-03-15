import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// Mock react-query to return test data
vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn().mockReturnValue({
    data: {
      id: "elem-1",
      name: "test_element",
      data_type: "string",
      description: "A test element",
      required: false,
      multivalued: false,
      source: { id: "src-1", name: "BIDS", version_tag: "1.0" },
      alias_count: 1,
      mapping_count: 1,
      version_num: 1,
      allowed_values: null,
      constraints: {},
      alias_groups: [
        { id: "ag-1", name: "age_group", member_count: 2, sssom_predicate: "skos:exactMatch" },
      ],
      mappings_as_input: [
        { id: "m-1", function_type: "identity", output_name: "subject_age" },
      ],
      mappings_as_output: [],
      created_at: "2026-03-01T00:00:00Z",
      deleted_at: null,
    },
    error: null,
    isLoading: false,
  }),
}));

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// Import after mocks
import { RelationshipGraph } from "@/components/RelationshipGraph";

describe("RelationshipGraph", () => {
  afterEach(() => cleanup());

  it("renders fallback table when Cytoscape not loaded", () => {
    render(<RelationshipGraph elementId="elem-1" />);
    // Should render the table fallback since Cytoscape dynamic import won't resolve in jsdom
    expect(screen.getByText("Node")).toBeInTheDocument();
    expect(screen.getByText("Type")).toBeInTheDocument();
    expect(screen.getByText("Relation")).toBeInTheDocument();
  });

  it("renders alias nodes in fallback table", () => {
    render(<RelationshipGraph elementId="elem-1" />);
    expect(screen.getByText("age_group")).toBeInTheDocument();
  });

  it("renders mapping nodes in fallback table", () => {
    render(<RelationshipGraph elementId="elem-1" />);
    expect(screen.getByText("subject_age")).toBeInTheDocument();
  });

  it("renders depth slider", () => {
    render(<RelationshipGraph elementId="elem-1" />);
    expect(screen.getByLabelText("Graph depth")).toBeInTheDocument();
  });
});
