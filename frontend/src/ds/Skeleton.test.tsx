import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Skeleton } from "./Skeleton";

describe("Skeleton", () => {
  it("renders a div", () => {
    const { container } = render(<Skeleton style={{ width: 100, height: 20 }} />);
    expect(container.firstChild).toBeInTheDocument();
  });
});
