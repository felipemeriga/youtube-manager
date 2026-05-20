import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "./Badge";

describe("Badge", () => {
  it("renders text", () => {
    render(<Badge>Done</Badge>);
    expect(screen.getByText("Done")).toBeInTheDocument();
  });
  it("supports tone variants", () => {
    render(<Badge tone="ok">A</Badge>);
    render(<Badge tone="danger" variant="solid">B</Badge>);
    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText("B")).toBeInTheDocument();
  });
});
