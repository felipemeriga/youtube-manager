import { describe, it, expect } from "vitest";
import { render, act } from "@testing-library/react";
import { StreamingTail } from "./StreamingTail";
import { createTokenStore } from "../lib/tokenStore";

describe("StreamingTail", () => {
  it("renders current store value and updates on append", () => {
    const store = createTokenStore();
    const { getByTestId } = render(
      <StreamingTail store={store} render={(t) => <div data-testid="t">{t}</div>} />,
    );
    expect(getByTestId("t").textContent).toBe("");
    act(() => store.append("hello"));
    expect(getByTestId("t").textContent).toBe("hello");
  });
});
