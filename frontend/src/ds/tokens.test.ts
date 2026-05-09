import { describe, it, expect } from "vitest";
import { palette, spacing, radius, motion, typography, focusRing } from "./tokens";

describe("design tokens", () => {
  it("exposes palette layers", () => {
    expect(palette.bg.canvas).toMatch(/^#/);
    expect(palette.accent[500]).toMatch(/^#/);
  });
  it("spacing scale uses 4px base", () => {
    expect(spacing(2)).toBe("8px");
    expect(spacing(0.5)).toBe("2px");
  });
  it("radius default is 10", () => {
    expect(radius.lg).toBe("10px");
  });
  it("motion has named durations", () => {
    expect(motion.duration.base).toBe("180ms");
  });
  it("typography exposes mono numeric variant", () => {
    expect(typography.scale.numeric.fontVariantNumeric).toBe("tabular-nums");
  });
  it("focus ring is keyboard-only style", () => {
    expect(focusRing.outline).toBe("none");
    expect(focusRing.boxShadow).toMatch(/(#|rgb)/);
  });
});
