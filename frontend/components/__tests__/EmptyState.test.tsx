import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { EmptyState } from "@/components/layout/EmptyState";

describe("EmptyState", () => {
  it("renders the title", () => {
    render(<EmptyState title="No orders yet" />);
    expect(screen.getByText("No orders yet")).toBeInTheDocument();
  });

  it("renders the description when provided", () => {
    render(
      <EmptyState
        title="No orders yet"
        description="Upload an Amazon order export to get started."
      />,
    );
    expect(
      screen.getByText("Upload an Amazon order export to get started."),
    ).toBeInTheDocument();
  });

  it("renders the action button when provided", () => {
    render(
      <EmptyState
        title="No orders yet"
        action={<button>Upload file</button>}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Upload file" }),
    ).toBeInTheDocument();
  });

  it("omits the description when not provided", () => {
    render(<EmptyState title="No orders yet" />);
    expect(screen.queryByText(/upload/i)).toBeNull();
  });
});
