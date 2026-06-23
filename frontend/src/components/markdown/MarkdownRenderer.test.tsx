import { render, screen } from "@testing-library/react";

import { MarkdownRenderer } from "./MarkdownRenderer";

describe("MarkdownRenderer", () => {
  it("renders markdown with heading anchors", () => {
    render(<MarkdownRenderer content={"# Title\n\nParagraph"} />);

    expect(screen.getByRole("heading", { name: /title/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "#" })).toBeInTheDocument();
    expect(screen.getByText("Paragraph")).toBeInTheDocument();
  });

  it("sanitizes dangerous html but keeps safe tags", () => {
    render(
      <MarkdownRenderer
        content={'<script>alert("xss")</script><mark>safe html</mark>'}
      />,
    );

    expect(screen.queryByText(/alert\("xss"\)/i)).not.toBeInTheDocument();
    expect(screen.getByText("safe html")).toBeInTheDocument();
  });
});
