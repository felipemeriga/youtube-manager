import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Textarea } from "./Textarea";

describe("Textarea", () => {
  it("renders with placeholder", () => {
    render(<Textarea placeholder="notes" />);
    expect(screen.getByPlaceholderText("notes")).toBeInTheDocument();
  });
});
