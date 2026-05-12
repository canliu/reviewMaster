import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import {
  STATUS_BADGE_MAP,
  StatusBadge,
} from "@/components/data/StatusBadge";

describe("StatusBadge", () => {
  it("renders 'Requested · manual' in info colors for sent+manual", () => {
    render(<StatusBadge status="sent" method="manual" />);
    const badge = screen.getByText(STATUS_BADGE_MAP.sent_manual.label);
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("text-info");
  });

  it("renders 'Requested · API' in success colors for sent+api", () => {
    render(<StatusBadge status="sent" method="api" />);
    const badge = screen.getByText(STATUS_BADGE_MAP.sent_api.label);
    expect(badge.className).toContain("text-success");
  });

  it("renders 'Pending' in warning colors", () => {
    render(<StatusBadge status="pending" />);
    expect(screen.getByText("Pending").className).toContain("text-warning");
  });

  it("renders 'Failed' in danger colors", () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByText("Failed").className).toContain("text-danger");
  });

  it("returns null when status is null and showEmpty is false", () => {
    const { container } = render(<StatusBadge status={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders 'Not requested' when status is null and showEmpty is true", () => {
    render(<StatusBadge status={null} showEmpty />);
    expect(screen.getByText("Not requested")).toBeInTheDocument();
  });
});
