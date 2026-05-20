import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("renders title and body", () => {
    render(<EmptyState title="No clips yet" body="Create your first clip" />);
    expect(screen.getByText("No clips yet")).toBeInTheDocument();
    expect(screen.getByText("Create your first clip")).toBeInTheDocument();
  });
});
