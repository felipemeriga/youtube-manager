import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Tooltip } from "./Tooltip";

describe("Tooltip", () => {
  it("renders child", () => {
    render(<Tooltip title="hint"><button>x</button></Tooltip>);
    expect(screen.getByRole("button", { name: "x" })).toBeInTheDocument();
  });
});
