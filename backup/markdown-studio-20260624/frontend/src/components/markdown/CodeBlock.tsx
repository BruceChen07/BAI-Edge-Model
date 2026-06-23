import { useEffect, useMemo, useState } from "react";
import { Button, Tag, Tooltip } from "antd";

import { MermaidBlock } from "./MermaidBlock";
import { normalizeFenceLanguage } from "./markdownUtils";

type SyntaxHighlighterModule = typeof import("react-syntax-highlighter");
type SyntaxHighlighterStylesModule =
  typeof import("react-syntax-highlighter/dist/esm/styles/prism");

type CodeBlockProps = {
  className?: string;
  children?: React.ReactNode;
  inline?: boolean;
  mode: "light" | "dark";
};

export function CodeBlock({
  className,
  children,
  inline,
  mode,
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const [syntaxHighlighter, setSyntaxHighlighter] = useState<
    SyntaxHighlighterModule["Prism"] | null
  >(null);
  const [syntaxStyles, setSyntaxStyles] =
    useState<SyntaxHighlighterStylesModule | null>(null);
  const rawCode = String(children ?? "").replace(/\n$/, "");
  const language = useMemo(() => {
    const matched = /language-(\w[\w-]*)/.exec(className ?? "");
    return normalizeFenceLanguage(matched?.[1] ?? "text");
  }, [className]);

  useEffect(() => {
    let cancelled = false;

    async function loadHighlighter() {
      const [{ Prism }, styles] = await Promise.all([
        import("react-syntax-highlighter"),
        import("react-syntax-highlighter/dist/esm/styles/prism"),
      ]);

      if (!cancelled) {
        setSyntaxHighlighter(() => Prism);
        setSyntaxStyles(styles);
      }
    }

    void loadHighlighter();
    return () => {
      cancelled = true;
    };
  }, []);

  if (inline) {
    return <code className={className}>{children}</code>;
  }

  if (language === "mermaid") {
    return <MermaidBlock chart={rawCode} mode={mode} />;
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(rawCode);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  const SyntaxHighlighter = syntaxHighlighter;
  const syntaxStyle =
    mode === "dark" ? syntaxStyles?.oneDark : syntaxStyles?.oneLight;

  return (
    <div className="markdown-code-block">
      <div className="markdown-code-toolbar">
        <div className="markdown-code-toolbar-meta">
          <Tag color="blue">{language}</Tag>
          <span className="markdown-code-toolbar-label">
            Syntax highlighting enabled
          </span>
        </div>
        <Tooltip title={copied ? "Copied" : "Copy code"}>
          <Button size="small" onClick={() => void handleCopy()}>
            {copied ? "Copied" : "Copy"}
          </Button>
        </Tooltip>
      </div>
      {SyntaxHighlighter && syntaxStyle ? (
        <SyntaxHighlighter
          language={language}
          style={syntaxStyle}
          showLineNumbers
          wrapLongLines
          customStyle={{ margin: 0, background: "transparent" }}
          lineNumberStyle={{
            minWidth: "2.5em",
            color: mode === "dark" ? "#64748b" : "#94a3b8",
          }}
        >
          {rawCode}
        </SyntaxHighlighter>
      ) : (
        <pre className="markdown-code-fallback">
          <code>{rawCode}</code>
        </pre>
      )}
    </div>
  );
}
