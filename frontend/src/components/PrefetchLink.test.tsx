import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { PrefetchLink } from "./PrefetchLink";

describe("PrefetchLink", () => {
  it("renders a router Link", () => {
    const { getByText } = render(
      <MemoryRouter>
        <PrefetchLink to="/assets">go</PrefetchLink>
      </MemoryRouter>,
    );
    expect(getByText("go")).toBeInTheDocument();
  });

  it("does not throw on hover", async () => {
    const { getByText } = render(
      <MemoryRouter>
        <PrefetchLink to="/clips">x</PrefetchLink>
      </MemoryRouter>,
    );
    await userEvent.hover(getByText("x"));
  });
});
