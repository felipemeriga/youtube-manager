import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Toast } from "./Toast";

describe("Toast", () => {
  it("renders message with status role", () => {
    render(<Toast tone="success">Saved!</Toast>);
    expect(screen.getByRole("status")).toHaveTextContent("Saved!");
  });
});
