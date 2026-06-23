const FENCE_PATTERN = /^```/;
const LATEX_BLOCK_PATTERN = /^\$\$/;
const TABLE_ROW_PATTERN = /^\|.*\|$/;
const TABLE_SEPARATOR_PATTERN = /^\|?[\s:-|]+\|?$/;

export const MERMAID_LANGUAGES = new Set([
  "mermaid",
  "mindmap",
  "flowchart",
  "journey",
  "sequence",
  "classdiagram",
  "stateDiagram",
  "gantt",
  "pie",
  "gitgraph",
]);

export function normalizeFenceLanguage(language: string): string {
  const normalized = language.trim().toLowerCase();
  return MERMAID_LANGUAGES.has(normalized) ? "mermaid" : normalized;
}

export function segmentMarkdownSections(markdown: string): string[] {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const sections: string[] = [];
  let buffer: string[] = [];
  let inFence = false;
  let inMathBlock = false;
  let inTable = false;

  const flush = () => {
    const content = buffer.join("\n").trim();
    if (content) {
      sections.push(content);
    }
    buffer = [];
  };

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const trimmed = line.trim();

    if (FENCE_PATTERN.test(trimmed)) {
      inFence = !inFence;
      buffer.push(line);
      if (!inFence) {
        flush();
      }
      continue;
    }

    if (!inFence && LATEX_BLOCK_PATTERN.test(trimmed)) {
      inMathBlock = !inMathBlock;
      buffer.push(line);
      if (!inMathBlock) {
        flush();
      }
      continue;
    }

    const nextLine = lines[index + 1]?.trim() ?? "";
    const isTableStart =
      !inFence &&
      !inMathBlock &&
      TABLE_ROW_PATTERN.test(trimmed) &&
      TABLE_SEPARATOR_PATTERN.test(nextLine);

    if (isTableStart && buffer.length > 0) {
      flush();
    }

    if (isTableStart) {
      inTable = true;
    }

    buffer.push(line);

    if (inTable) {
      const followingLine = lines[index + 1]?.trim();
      const shouldEndTable =
        followingLine === undefined || !TABLE_ROW_PATTERN.test(followingLine);
      if (shouldEndTable) {
        flush();
        inTable = false;
      }
      continue;
    }

    if (!inFence && !inMathBlock && trimmed === "") {
      flush();
    }
  }

  flush();
  return sections.length > 0 ? sections : [markdown];
}

export function shouldUseVirtualizedMarkdown(markdown: string): boolean {
  return markdown.length >= 8000 || segmentMarkdownSections(markdown).length > 18;
}

export function parseThemeOverrideInput(
  rawValue: string,
): Record<string, string> | null {
  if (!rawValue.trim()) {
    return {};
  }

  try {
    const parsed = JSON.parse(rawValue) as Record<string, unknown>;
    const normalized: Record<string, string> = {};
    Object.entries(parsed).forEach(([key, value]) => {
      if (typeof value === "string") {
        normalized[key] = value;
      }
    });
    return normalized;
  } catch {
    return null;
  }
}

export function buildLongMarkdownSample(seed: string, repeatCount = 40): string {
  return Array.from({ length: repeatCount }, (_, index) => {
    const chapter = index + 1;
    return `## Long Section ${chapter}\n\n${seed}\n\n- Iteration marker: ${chapter}\n- Streaming chunk index: ${chapter}\n- Estimated payload size: ${seed.length}\n`;
  }).join("\n");
}
