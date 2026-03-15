import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SearchBar } from "@/components/SearchBar";

describe("SearchBar", () => {
  afterEach(() => cleanup());

  it("renders a search input", () => {
    render(<SearchBar onSearch={vi.fn()} />);
    expect(screen.getByLabelText("Search elements")).toBeInTheDocument();
  });

  it("debounces — calls onSearch after 300ms", () => {
    vi.useFakeTimers();
    const onSearch = vi.fn();
    render(<SearchBar onSearch={onSearch} />);
    const input = screen.getByLabelText("Search elements");
    fireEvent.change(input, { target: { value: "age" } });
    expect(onSearch).not.toHaveBeenCalled();
    vi.advanceTimersByTime(300);
    expect(onSearch).toHaveBeenCalledWith("age");
    vi.useRealTimers();
  });

  it("shows clear button when input has value", () => {
    const onSearch = vi.fn();
    render(<SearchBar onSearch={onSearch} />);
    expect(screen.queryByText("Clear")).not.toBeInTheDocument();
    const input = screen.getByLabelText("Search elements");
    fireEvent.change(input, { target: { value: "test" } });
    expect(screen.getByText("Clear")).toBeInTheDocument();
  });

  it("clears query on clear button click", () => {
    vi.useFakeTimers();
    const onSearch = vi.fn();
    render(<SearchBar onSearch={onSearch} />);
    const input = screen.getByLabelText("Search elements") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.click(screen.getByText("Clear"));
    expect(input.value).toBe("");
    expect(onSearch).toHaveBeenCalledWith("");
    vi.useRealTimers();
  });

  it("trims input to 500 chars", () => {
    const onSearch = vi.fn();
    render(<SearchBar onSearch={onSearch} />);
    const input = screen.getByLabelText("Search elements") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "a".repeat(600) } });
    expect(input.value.length).toBeLessThanOrEqual(500);
  });
});
