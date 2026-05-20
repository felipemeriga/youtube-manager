import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PageHeader } from "./PageHeader";

describe("PageHeader", () => {
  it("renders title as h1", () => {
    render(<PageHeader title="Clips" />);
    expect(screen.getByRole("heading", { level: 1, name: "Clips" })).toBeInTheDocument();
  });
  it("renders eyebrow + subtitle + actions when provided", () => {
    render(
      <PageHeader
        eyebrow="WORKSPACE"
        title="Assets"
        subtitle="42 files"
        actions={<button>Upload</button>}
      />,
    );
    expect(screen.getByText("WORKSPACE")).toBeInTheDocument();
    expect(screen.getByText("42 files")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload" })).toBeInTheDocument();
  });
});
