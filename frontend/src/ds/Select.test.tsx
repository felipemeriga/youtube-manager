import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Select } from "./Select";

describe("Select", () => {
  it("renders options", () => {
    render(
      <Select aria-label="x">
        <option value="a">A</option>
        <option value="b">B</option>
      </Select>,
    );
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });
});
