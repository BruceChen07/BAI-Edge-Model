import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, ComponentPropsWithoutRef } from "react";
import { Alert } from "antd";
import { useVirtualizer } from "@tanstack/react-virtual";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";

import { CodeBlock } from "./CodeBlock";
import {
  type MarkdownThemeName,
  type MarkdownThemeOverride,
  resolveMarkdownTheme,
  themeTokensToCssVars,
} from "./markdownThemes";
import {
  segmentMarkdownSections,
  shouldUseVirtualizedMarkdown,
} from "./markdownUtils";

type MarkdownRendererProps = {
  content: string;
  themeName?: MarkdownThemeName;
  customTheme?: MarkdownThemeOverride;
  className?: string;
  style?: CSSProperties;
  enableHtml?: boolean;
  enableVirtualization?: boolean;
  streaming?: boolean;
  height?: number;
};

const markdownSanitizeSchema = {
  ...defaultSchema,
  tagNames: [
    ...(defaultSchema.tagNames ?? []),
    "div",
    "span",
    "section",
    "article",
    "details",
    "summary",
    "kbd",
    "mark",
    "sup",
    "sub",
  ],
  attributes: {
    ...(defaultSchema.attributes ?? {}),
    "*": [
      ...((defaultSchema.attributes?.["*"] as Array<string | RegExp>) ?? []),
      "className",
      "id",
      "title",
    ],
    a: [
      ...((defaultSchema.attributes?.a as Array<string | RegExp>) ?? []),
      "href",
      "target",
      "rel",
    ],
    code: [
      ...((defaultSchema.attributes?.code as Array<string | RegExp>) ?? []),
      "className",
    ],
    span: [
      ...((defaultSchema.attributes?.span as Array<string | RegExp>) ?? []),
      "className",
    ],
    div: ["className"],
    img: [
      ...((defaultSchema.attributes?.img as Array<string | RegExp>) ?? []),
      "src",
      "alt",
      "title",
      "width",
      "height",
      "loading",
    ],
  },
};

function MarkdownSectionRenderer({
  content,
  mode,
  enableHtml,
}: {
  content: string;
  mode: "light" | "dark";
  enableHtml: boolean;
}) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={
        enableHtml
          ? [rehypeRaw, rehypeKatex, [rehypeSanitize, markdownSanitizeSchema]]
          : [rehypeKatex]
      }
      components={{
        code: ({ className, children, ...props }) => (
          <CodeBlock className={className} mode={mode} {...props}>
            {children}
          </CodeBlock>
        ),
        table: ({ children }) => (
          <div className="markdown-table-scroll">
            <table>{children}</table>
          </div>
        ),
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noreferrer noopener">
            {children}
          </a>
        ),
        h1: HeadingWithAnchor("h1"),
        h2: HeadingWithAnchor("h2"),
        h3: HeadingWithAnchor("h3"),
        h4: HeadingWithAnchor("h4"),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

function HeadingWithAnchor(tag: "h1" | "h2" | "h3" | "h4") {
  return function Heading({
    children,
    ...props
  }: ComponentPropsWithoutRef<typeof tag>) {
    const text = String(children).trim();
    const anchor = text
      .toLowerCase()
      .replace(/[^\w\u4e00-\u9fa5]+/g, "-")
      .replace(/^-+|-+$/g, "");
    const Tag = tag;
    return (
      <Tag id={anchor} {...props}>
        <a className="markdown-heading-anchor" href={`#${anchor}`}>
          #
        </a>
        <span>{children}</span>
      </Tag>
    );
  };
}

function VirtualizedMarkdown({
  sections,
  height,
  mode,
  enableHtml,
  streaming,
}: {
  sections: string[];
  height: number;
  mode: "light" | "dark";
  enableHtml: boolean;
  streaming: boolean;
}) {
  const parentRef = useRef<HTMLDivElement | null>(null);
  const [visibleCount, setVisibleCount] = useState(
    streaming ? 6 : sections.length,
  );

  useEffect(() => {
    if (!streaming) {
      setVisibleCount(sections.length);
      return;
    }

    let cancelled = false;
    let frameId = 0;

    const step = () => {
      if (cancelled) {
        return;
      }
      setVisibleCount((current) => {
        const next = Math.min(current + 4, sections.length);
        if (next < sections.length) {
          frameId = window.requestAnimationFrame(step);
        }
        return next;
      });
    };

    frameId = window.requestAnimationFrame(step);
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(frameId);
    };
  }, [sections.length, streaming]);

  const activeSections = sections.slice(0, visibleCount);
  // eslint-disable-next-line react-hooks/incompatible-library
  const rowVirtualizer = useVirtualizer({
    count: activeSections.length,
    getScrollElement: () => parentRef.current,
    estimateSize: (index) => {
      const roughLength = activeSections[index]?.length ?? 0;
      return Math.max(120, Math.min(roughLength / 2, 360));
    },
    overscan: 4,
  });

  return (
    <div
      ref={parentRef}
      className="markdown-virtualized-shell"
      style={{ height }}
    >
      <div
        style={{
          height: `${rowVirtualizer.getTotalSize()}px`,
          position: "relative",
        }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => (
          <div
            key={virtualRow.key}
            data-index={virtualRow.index}
            ref={rowVirtualizer.measureElement}
            className="markdown-virtualized-row"
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              transform: `translateY(${virtualRow.start}px)`,
            }}
          >
            <MarkdownSectionRenderer
              content={activeSections[virtualRow.index]}
              mode={mode}
              enableHtml={enableHtml}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

export function MarkdownRenderer({
  content,
  themeName = "light",
  customTheme,
  className,
  style,
  enableHtml = true,
  enableVirtualization = true,
  streaming = false,
  height = 520,
}: MarkdownRendererProps) {
  const theme = resolveMarkdownTheme(themeName, customTheme);
  const sections = useMemo(() => segmentMarkdownSections(content), [content]);
  const shouldVirtualize =
    enableVirtualization && shouldUseVirtualizedMarkdown(content);

  if (!content.trim()) {
    return (
      <Alert
        type="info"
        showIcon
        message="暂无 Markdown 内容"
        description="等待大模型返回内容后再进行渲染。"
      />
    );
  }

  return (
    <article
      className={`markdown-renderer markdown-theme-${theme.name}${className ? ` ${className}` : ""}`}
      style={{
        ...themeTokensToCssVars(theme),
        ...style,
      }}
      data-theme-mode={theme.mode}
    >
      {shouldVirtualize ? (
        <VirtualizedMarkdown
          sections={sections}
          height={height}
          mode={theme.mode}
          enableHtml={enableHtml}
          streaming={streaming}
        />
      ) : (
        <div className="markdown-renderer-body">
          <MarkdownSectionRenderer
            content={content}
            mode={theme.mode}
            enableHtml={enableHtml}
          />
        </div>
      )}
    </article>
  );
}
