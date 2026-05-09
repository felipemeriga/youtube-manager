import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { LazyImage } from "./LazyImage";

// Per-test mock: capture observer instances so we can fire intersection on demand.
class CapturedObserver {
  static instances: CapturedObserver[] = [];
  cb: IntersectionObserverCallback;
  constructor(cb: IntersectionObserverCallback) {
    this.cb = cb;
    CapturedObserver.instances.push(this);
  }
  observe = () => {};
  unobserve = () => {};
  disconnect = () => {};
  takeRecords = () => [];
  root = null;
  rootMargin = "";
  thresholds = [];
  fire() {
    this.cb([{ isIntersecting: true } as IntersectionObserverEntry], this as unknown as IntersectionObserver);
  }
}

let originalIO: typeof IntersectionObserver;

beforeEach(() => {
  originalIO = (globalThis as unknown as { IntersectionObserver: typeof IntersectionObserver })
    .IntersectionObserver;
  (globalThis as unknown as { IntersectionObserver: typeof IntersectionObserver }).IntersectionObserver =
    CapturedObserver as unknown as typeof IntersectionObserver;
  CapturedObserver.instances = [];
});

afterEach(() => {
  (globalThis as unknown as { IntersectionObserver: typeof IntersectionObserver }).IntersectionObserver =
    originalIO;
});

describe("LazyImage", () => {
  it("renders a skeleton placeholder before intersection", () => {
    render(<LazyImage src="/x.jpg" alt="x" widths={[200, 400]} />);
    expect(screen.getByTestId("lazyimage-skeleton")).toBeInTheDocument();
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("renders the image with srcset on intersection", () => {
    render(<LazyImage src="/img.jpg" alt="x" widths={[200, 400, 800]} />);
    const obs = CapturedObserver.instances[0];
    act(() => obs.fire());
    const img = screen.getByRole("img");
    expect(img.getAttribute("srcset")).toMatch(/200w/);
    expect(img.getAttribute("srcset")).toMatch(/800w/);
    expect(img.getAttribute("loading")).toBe("lazy");
  });
});
