import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatCell } from "./StatCell";

describe("StatCell", () => {
  it("renders label and value", () => {
    render(<StatCell label="ACTIVE" value="42" />);
    expect(screen.getByText("ACTIVE")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });
});
