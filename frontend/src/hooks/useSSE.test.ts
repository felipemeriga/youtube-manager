import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useSSE } from "./useSSE";

describe("useSSE", () => {
  it("does nothing when disabled", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    fetchSpy.mockClear();
    renderHook(() => useSSE({ url: "/x", enabled: false, onEvent: () => {} }));
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
