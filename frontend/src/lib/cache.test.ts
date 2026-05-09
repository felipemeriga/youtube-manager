import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useCachedQuery, clearCache, invalidate, getCached, setCached } from "./cache";

describe("cache", () => {
  beforeEach(() => clearCache());

  it("fetches once and returns data", async () => {
    const fetcher = vi.fn().mockResolvedValue({ x: 1 });
    const { result } = renderHook(() => useCachedQuery("k1", fetcher));
    await waitFor(() => expect(result.current.data).toEqual({ x: 1 }));
    expect(fetcher).toHaveBeenCalledOnce();
  });

  it("dedupes concurrent fetches by key", async () => {
    const fetcher = vi
      .fn()
      .mockImplementation(() => new Promise((r) => setTimeout(() => r({ y: 2 }), 20)));
    renderHook(() => useCachedQuery("k2", fetcher));
    renderHook(() => useCachedQuery("k2", fetcher));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
  });

  it("invalidate removes prefixed keys", () => {
    setCached("conv:1", "a");
    setCached("conv:2", "b");
    setCached("user", "u");
    invalidate("conv:");
    expect(getCached("conv:1")).toBeUndefined();
    expect(getCached("user")).toBe("u");
  });
});
