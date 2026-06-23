import {
  buildLongMarkdownSample,
  parseThemeOverrideInput,
  segmentMarkdownSections,
  shouldUseVirtualizedMarkdown,
} from "./markdownUtils";

describe("markdownUtils", () => {
  it("keeps fenced blocks intact when splitting sections", () => {
    const markdown = [
      "# Title",
      "",
      "```ts",
      "const value = 1;",
      "```",
      "",
      "Paragraph",
    ].join("\n");

    const sections = segmentMarkdownSections(markdown);

    expect(sections).toHaveLength(3);
    expect(sections[1]).toContain("```ts");
    expect(sections[1]).toContain("const value = 1;");
  });

  it("keeps markdown tables in a single section", () => {
    const markdown = [
      "| A | B |",
      "|---|---|",
      "| 1 | 2 |",
      "",
      "tail",
    ].join("\n");

    const sections = segmentMarkdownSections(markdown);

    expect(sections[0]).toContain("| 1 | 2 |");
    expect(sections[1]).toBe("tail");
  });

  it("parses custom theme overrides safely", () => {
    expect(parseThemeOverrideInput('{"link":"#123456","surface":"#ffffff"}'))
      .toEqual({
        link: "#123456",
        surface: "#ffffff",
      });
    expect(parseThemeOverrideInput("{invalid")).toBeNull();
  });

  it("switches to virtualization for long markdown content", () => {
    const longMarkdown = buildLongMarkdownSample("content", 100);
    expect(shouldUseVirtualizedMarkdown(longMarkdown)).toBe(true);
  });
});
