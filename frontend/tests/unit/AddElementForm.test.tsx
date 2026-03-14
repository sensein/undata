import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Mock next/navigation
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

// Mock API calls
vi.mock("@/lib/api/sources", () => ({
  getSources: vi.fn().mockResolvedValue([
    { id: "src-1", name: "BIDS" },
    { id: "src-2", name: "NWB" },
  ]),
}));

vi.mock("@/lib/api/elements", () => ({
  getElements: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  createElement: vi.fn().mockResolvedValue({ id: "new-elem-1" }),
}));

import { AddElementForm } from "@/components/AddElementForm";

function renderWithProviders(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

describe("AddElementForm", () => {
  afterEach(() => {
    cleanup();
    pushMock.mockClear();
  });

  it("renders all required fields", () => {
    renderWithProviders(<AddElementForm />);
    expect(screen.getByLabelText("Name *")).toBeInTheDocument();
    expect(screen.getByLabelText("Data Type *")).toBeInTheDocument();
    expect(screen.getByLabelText("Description *")).toBeInTheDocument();
    expect(screen.getByLabelText("Source *")).toBeInTheDocument();
    expect(screen.getByLabelText("Required")).toBeInTheDocument();
    expect(screen.getByLabelText("Multivalued")).toBeInTheDocument();
  });

  it("shows error when submitting with missing description", () => {
    renderWithProviders(<AddElementForm />);
    const nameInput = screen.getByLabelText("Name *");
    fireEvent.change(nameInput, { target: { value: "test_element" } });
    fireEvent.click(screen.getByText("Create Element"));
    expect(screen.getByText("Description is required")).toBeInTheDocument();
  });

  it("shows error when name exceeds 200 chars", () => {
    renderWithProviders(<AddElementForm />);
    const nameInput = screen.getByLabelText("Name *");
    fireEvent.change(nameInput, { target: { value: "a".repeat(201) } });
    fireEvent.click(screen.getByText("Create Element"));
    expect(
      screen.getByText("Name must be 200 characters or fewer"),
    ).toBeInTheDocument();
  });

  it("shows error when description is too short", () => {
    renderWithProviders(<AddElementForm />);
    fireEvent.change(screen.getByLabelText("Name *"), {
      target: { value: "test_el" },
    });
    fireEvent.change(screen.getByLabelText("Description *"), {
      target: { value: "short" },
    });
    fireEvent.click(screen.getByText("Create Element"));
    expect(
      screen.getByText("Description must be at least 10 characters"),
    ).toBeInTheDocument();
  });

  it("shows error when source is not selected", () => {
    renderWithProviders(<AddElementForm />);
    fireEvent.change(screen.getByLabelText("Name *"), {
      target: { value: "test_el" },
    });
    fireEvent.change(screen.getByLabelText("Description *"), {
      target: { value: "A valid description for testing" },
    });
    fireEvent.click(screen.getByText("Create Element"));
    expect(screen.getByText("Source is required")).toBeInTheDocument();
  });
});
