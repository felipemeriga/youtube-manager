import { describe, it, expect } from "vitest";

describe("test infrastructure", () => {
  it("runs a basic assertion", () => {
    expect(1 + 1).toBe(2);
  });

  it("has matchMedia mock", () => {
    expect(window.matchMedia("(prefers-color-scheme: dark)")).toBeDefined();
  });

  it("has IntersectionObserver mock", () => {
    expect(globalThis.IntersectionObserver).toBeDefined();
  });
});
