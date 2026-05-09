import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ListRow } from "./ListRow";

describe("ListRow", () => {
  it("renders content + meta + trailing", () => {
    render(
      <ListRow leading={<span>L</span>} meta="2m" trailing={<span>T</span>}>
        Title
      </ListRow>,
    );
    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getByText("2m")).toBeInTheDocument();
  });
  it("interactive exposes button role", () => {
    render(<ListRow interactive>X</ListRow>);
    expect(screen.getByRole("button")).toBeInTheDocument();
  });
});
