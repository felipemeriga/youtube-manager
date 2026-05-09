import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Card } from "./Card";

describe("Card", () => {
  it("renders children", () => {
    const { getByText } = render(<Card>hello</Card>);
    expect(getByText("hello")).toBeInTheDocument();
  });
  it("applies flush", () => {
    const { container } = render(<Card flush>x</Card>);
    expect(container.firstChild).toHaveStyle({ padding: "0px" });
  });
});
