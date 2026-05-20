import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Inline } from "./Inline";

describe("Inline", () => {
  it("renders children", () => {
    const { getByText } = render(<Inline><span>a</span></Inline>);
    expect(getByText("a")).toBeInTheDocument();
  });
  it("wraps when prop set", () => {
    const { container } = render(<Inline wrap>x</Inline>);
    expect(container.firstChild).toHaveStyle({ flexWrap: "wrap" });
  });
});
