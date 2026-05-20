import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Stack } from "./Stack";

describe("Stack", () => {
  it("renders children", () => {
    const { getByText } = render(<Stack><span>a</span></Stack>);
    expect(getByText("a")).toBeInTheDocument();
  });
  it("applies gap from prop", () => {
    const { container } = render(<Stack gap={3}>x</Stack>);
    expect(container.firstChild).toHaveStyle({ gap: "12px" });
  });
});
