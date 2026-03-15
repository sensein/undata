import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ComparisonView } from "@/components/ComparisonView";
import type { DataElementDetail } from "@/lib/types";

vi.mock("@/lib/api/aliases", () => ({
  registerAlias: vi.fn().mockResolvedValue({ id: "alias-1" }),
}));

const baseElement: DataElementDetail = {
  id: "elem-1",
  name: "subject_age",
  data_type: "number",
  description: "Age of participant",
  required: true,
  multivalued: false,
  source: { id: "src-1", name: "BIDS", version_tag: "1.0" },
  alias_count: 0,
  mapping_count: 0,
  version_num: 1,
  allowed_values: null,
  constraints: {},
  alias_groups: [],
  mappings_as_input: [],
  mappings_as_output: [],
  created_at: "2026-03-01T00:00:00Z",
  deleted_at: null,
};

function renderWithProviders(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

describe("ComparisonView", () => {
  afterEach(() => cleanup());

  it("renders two columns with element names", () => {
    const elB = { ...baseElement, id: "elem-2", name: "participant_age" };
    renderWithProviders(
      <ComparisonView elementA={baseElement} elementB={elB} />,
    );
    // Names appear in header and in the Name row — use getAllByText
    expect(screen.getAllByText("subject_age").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("participant_age").length).toBeGreaterThanOrEqual(1);
  });

  it("marks identical field values as matching", () => {
    const elB = { ...baseElement, id: "elem-2", name: "participant_age" };
    renderWithProviders(
      <ComparisonView elementA={baseElement} elementB={elB} />,
    );
    // data_type is "number" for both — should be matching
    const matchIcons = screen.getAllByLabelText("matching");
    expect(matchIcons.length).toBeGreaterThan(0);
  });

  it("marks differing field values as differs", () => {
    const elB = {
      ...baseElement,
      id: "elem-2",
      name: "participant_age",
      data_type: "string",
    };
    renderWithProviders(
      <ComparisonView elementA={baseElement} elementB={elB} />,
    );
    const diffIcons = screen.getAllByLabelText("differs");
    expect(diffIcons.length).toBeGreaterThan(0);
  });

  it("disables Register as Alias button when data types differ", () => {
    const elB = {
      ...baseElement,
      id: "elem-2",
      name: "participant_age",
      data_type: "string",
    };
    renderWithProviders(
      <ComparisonView elementA={baseElement} elementB={elB} />,
    );
    const button = screen.getByText("Register as Alias");
    expect(button).toBeDisabled();
  });

  it("enables Register as Alias button when data types match", () => {
    const elB = { ...baseElement, id: "elem-2", name: "participant_age" };
    renderWithProviders(
      <ComparisonView elementA={baseElement} elementB={elB} />,
    );
    const button = screen.getByText("Register as Alias");
    expect(button).not.toBeDisabled();
  });
});
