import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SectionHeader } from "./SectionHeader";

describe("SectionHeader", () => {
  it("renders title as h2", () => {
    render(<SectionHeader title="Recent" />);
    expect(screen.getByRole("heading", { level: 2, name: "Recent" })).toBeInTheDocument();
  });
});
