import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Input } from "./Input";

describe("Input", () => {
  it("renders with placeholder", () => {
    render(<Input placeholder="Email" />);
    expect(screen.getByPlaceholderText("Email")).toBeInTheDocument();
  });
  it("forwards onChange", async () => {
    const onChange = vi.fn();
    render(<Input placeholder="x" onChange={onChange} />);
    await userEvent.type(screen.getByPlaceholderText("x"), "ab");
    expect(onChange).toHaveBeenCalled();
  });
});
