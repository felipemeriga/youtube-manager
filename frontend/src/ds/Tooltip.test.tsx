import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Tooltip } from "./Tooltip";

describe("Tooltip", () => {
  it("renders child element", () => {
    // MUI's Tooltip wraps its child and applies aria-label from `title`, so
    // `getByRole("button", { name: "x" })` would fail. Assert the text content
    // is in the DOM and that the button is reachable.
    render(<Tooltip title="hint"><button>x</button></Tooltip>);
    expect(screen.getByText("x")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "hint" })).toBeInTheDocument();
  });
});
