import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Dialog, DialogContent, DialogTitle } from "./Dialog";

describe("Dialog", () => {
  it("renders title and content when open", () => {
    render(
      <Dialog open onClose={() => {}}>
        <DialogTitle>Title</DialogTitle>
        <DialogContent>Body</DialogContent>
      </Dialog>,
    );
    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getByText("Body")).toBeInTheDocument();
  });
});
