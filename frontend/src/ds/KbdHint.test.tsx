import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { KbdHint } from "./KbdHint";

describe("KbdHint", () => {
  it("renders kbd element", () => {
    render(<KbdHint>⌘K</KbdHint>);
    expect(screen.getByText("⌘K").tagName).toBe("KBD");
  });
});
