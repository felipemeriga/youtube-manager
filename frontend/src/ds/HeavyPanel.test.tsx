import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { HeavyPanel } from "./HeavyPanel";

describe("HeavyPanel", () => {
  it("renders children inside Suspense", () => {
    render(
      <HeavyPanel>
        <span>panel</span>
      </HeavyPanel>,
    );
    expect(screen.getByText("panel")).toBeInTheDocument();
  });
});
