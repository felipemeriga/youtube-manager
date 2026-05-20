import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { StatusDot } from "./StatusDot";

describe("StatusDot", () => {
  it("renders a span", () => {
    const { container } = render(<StatusDot tone="ok" />);
    expect(container.querySelector("span")).toBeInTheDocument();
  });
});
