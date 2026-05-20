import { describe, it, expect, vi } from "vitest";
import { createTokenStore } from "./tokenStore";

describe("tokenStore", () => {
  it("appends and notifies subscribers", () => {
    const s = createTokenStore();
    const l = vi.fn();
    const unsub = s.subscribe(l);
    s.append("hi ");
    s.append("there");
    expect(s.getSnapshot()).toBe("hi there");
    expect(l).toHaveBeenCalledTimes(2);
    unsub();
    s.append("!");
    expect(l).toHaveBeenCalledTimes(2);
  });

  it("resets value", () => {
    const s = createTokenStore();
    s.append("a");
    s.reset();
    expect(s.getSnapshot()).toBe("");
  });
});
