import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Pill } from "./Pill";

describe("Pill", () => {
  it("renders text", () => {
    render(<Pill>NEW</Pill>);
    expect(screen.getByText("NEW")).toBeInTheDocument();
  });
});
