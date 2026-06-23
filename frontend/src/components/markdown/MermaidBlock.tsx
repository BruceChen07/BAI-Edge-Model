import { useEffect, useId, useState } from "react";

type MermaidBlockProps = {
  chart: string;
  mode: "light" | "dark";
};

type MermaidRenderState =
  | { status: "loading" }
  | { status: "ready"; svg: string }
  | { status: "error"; message: string };

export function MermaidBlock({ chart, mode }: MermaidBlockProps) {
  const [renderState, setRenderState] = useState<MermaidRenderState>({
    status: "loading",
  });
  const chartId = `mermaid-${useId().replace(/:/g, "-")}`;

  useEffect(() => {
    let cancelled = false;

    async function renderChart() {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: mode === "dark" ? "dark" : "neutral",
        });

        const { svg } = await mermaid.render(chartId, chart);
        if (!cancelled) {
          setRenderState({ status: "ready", svg });
        }
      } catch (error) {
        if (!cancelled) {
          setRenderState({
            status: "error",
            message:
              error instanceof Error ? error.message : "Mermaid render failed.",
          });
        }
      }
    }

    void renderChart();

    return () => {
      cancelled = true;
    };
  }, [chart, chartId, mode]);

  if (renderState.status === "error") {
    return (
      <div className="markdown-mermaid-error" role="alert">
        <div className="markdown-mermaid-error-title">
          Mermaid render failed
        </div>
        <pre>{renderState.message}</pre>
        <pre>{chart}</pre>
      </div>
    );
  }

  if (renderState.status === "loading") {
    return (
      <div className="markdown-mermaid-loading" aria-busy="true">
        Rendering Mermaid diagram...
      </div>
    );
  }

  return (
    <div
      className="markdown-mermaid"
      dangerouslySetInnerHTML={{ __html: renderState.svg }}
    />
  );
}
