import { Suspense, lazy, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Input,
  Row,
  Segmented,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from "antd";

import type { Locale } from "../i18n/messages";
import {
  BUILTIN_MARKDOWN_THEMES,
  type MarkdownThemeName,
} from "../components/markdown/markdownThemes";
import {
  buildLongMarkdownSample,
  parseThemeOverrideInput,
} from "../components/markdown/markdownUtils";

const { Paragraph, Text, Title } = Typography;
const { TextArea } = Input;
const MarkdownRenderer = lazy(async () => ({
  default: (await import("../components/markdown/MarkdownRenderer"))
    .MarkdownRenderer,
}));

type MarkdownStudioPageProps = {
  locale: Locale;
};

const richMarkdownSample = `# BAI Edge Markdown Rendering Review

> 目标：让大模型输出的 Markdown 在聊天场景中具备「可读、可交互、可审计、可扩展」四个属性。

## 1. 复杂语法覆盖

| 语法 | 示例 | 渲染策略 |
|---|---|---|
| 代码块 | \`\`\`ts ... \`\`\` | 语法高亮 + 行号 + 复制 |
| 数学公式 | $$E = mc^2$$ | KaTeX |
| Mermaid | \`\`\`mermaid ... \`\`\` | 原生 Mermaid |
| 原生 HTML | <mark>highlight</mark> | 白名单清洗后渲染 |

### TypeScript Example

\`\`\`ts
type RenderPlan = {
  theme: "light" | "dark" | "eyeCare";
  virtualization: boolean;
  sanitize: "strict";
};

export function createRenderPlan(): RenderPlan {
  return {
    theme: "light",
    virtualization: true,
    sanitize: "strict",
  };
}
\`\`\`

### Formula Example

内联公式：$\\int_0^1 x^2 dx = 1/3$

块级公式：

$$
\\operatorname{score}(q, d) =
\\alpha \\cdot \\operatorname{fts5}(q, d) +
\\beta \\cdot \\operatorname{jaccard}(q, d)
$$

### Mermaid Flowchart

\`\`\`mermaid
flowchart LR
    Prompt[User Prompt] --> Parser[Markdown Pipeline]
    Parser --> Sanitize[rehype-sanitize]
    Sanitize --> RichUI[Renderer]
    RichUI --> VirtualList[Virtualized Sections]
    RichUI --> ThemeSystem[Theme Tokens]
\`\`\`

### Mermaid Mindmap

\`\`\`mermaid
mindmap
  root((Markdown UX))
    Theme
      Light
      Dark
      Eye Care
    Security
      XSS sanitize
      Safe HTML
    Performance
      Chunk render
      Virtual scroll
\`\`\`

### Safe HTML Example

<details>
  <summary>展开查看嵌入式 HTML 片段</summary>
  <div>
    <mark>合法 HTML 保留</mark>，脚本标签与危险属性会被过滤。
  </div>
</details>

### Checklist

- [x] Code copy
- [x] KaTeX
- [x] Mermaid
- [x] Responsive table
- [x] Theme switching
`;

const rendererComparisonRows = [
  {
    key: "react-markdown",
    library: "react-markdown + unified",
    completeness: "高",
    performance: "中高",
    ecosystem: "remark/rehype 插件生态最完整",
    fit: "推荐",
  },
  {
    key: "markdown-it",
    library: "markdown-it",
    completeness: "中高",
    performance: "高",
    ecosystem: "插件丰富，但 React 组件定制成本更高",
    fit: "备选",
  },
  {
    key: "marked",
    library: "marked",
    completeness: "中",
    performance: "高",
    ecosystem: "核心轻量，但安全与扩展能力依赖自组装",
    fit: "不作为主选",
  },
];

export function MarkdownStudioPage({ locale }: MarkdownStudioPageProps) {
  const [themeName, setThemeName] = useState<MarkdownThemeName>("light");
  const [showLongContent, setShowLongContent] = useState(false);
  const [streaming, setStreaming] = useState(true);
  const [customThemeInput, setCustomThemeInput] = useState("");

  const customTheme = useMemo(
    () => parseThemeOverrideInput(customThemeInput),
    [customThemeInput],
  );

  const previewMarkdown = useMemo(() => {
    if (!showLongContent) {
      return richMarkdownSample;
    }
    return buildLongMarkdownSample(richMarkdownSample, 60);
  }, [showLongContent]);

  const comparisonColumns = [
    { title: locale === "zh-CN" ? "方案" : "Library", dataIndex: "library" },
    {
      title: locale === "zh-CN" ? "功能完整性" : "Completeness",
      dataIndex: "completeness",
    },
    {
      title: locale === "zh-CN" ? "性能" : "Performance",
      dataIndex: "performance",
    },
    {
      title: locale === "zh-CN" ? "生态支持" : "Ecosystem",
      dataIndex: "ecosystem",
    },
    {
      title: locale === "zh-CN" ? "结论" : "Decision",
      dataIndex: "fit",
      render: (value: string) =>
        value === "推荐" || value === "Recommended" ? (
          <Tag color="green">{value}</Tag>
        ) : (
          <Tag>{value}</Tag>
        ),
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card>
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          <Title level={4} style={{ margin: 0 }}>
            Markdown Rendering Studio
          </Title>
          <Paragraph style={{ margin: 0 }}>
            审核演示页同时承担高保真原型职责，用于展示主题切换、复杂语法渲染、安全策略与长文本性能方案。
          </Paragraph>
          <Alert
            type="info"
            showIcon
            message="审核建议"
            description="先以标准样例检查视觉与交互，再切换到长文本模式验证虚拟滚动和分片渲染是否平滑。"
          />
        </Space>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card title="控制台" style={{ height: "100%" }}>
            <Space direction="vertical" size="middle" style={{ width: "100%" }}>
              <div>
                <Text strong>内置主题</Text>
                <div style={{ marginTop: 8 }}>
                  <Segmented<MarkdownThemeName>
                    block
                    value={themeName}
                    options={(
                      Object.keys(
                        BUILTIN_MARKDOWN_THEMES,
                      ) as MarkdownThemeName[]
                    ).map((key) => ({
                      label: BUILTIN_MARKDOWN_THEMES[key].label,
                      value: key,
                    }))}
                    onChange={(value) => setThemeName(value)}
                  />
                </div>
              </div>

              <div>
                <Text strong>长文本压测模式</Text>
                <div style={{ marginTop: 8 }}>
                  <Switch
                    checked={showLongContent}
                    onChange={setShowLongContent}
                    checkedChildren="10万字模拟"
                    unCheckedChildren="标准样例"
                  />
                </div>
              </div>

              <div>
                <Text strong>流式增量渲染</Text>
                <div style={{ marginTop: 8 }}>
                  <Switch checked={streaming} onChange={setStreaming} />
                </div>
              </div>

              <div>
                <Text strong>自定义主题 JSON</Text>
                <TextArea
                  rows={8}
                  value={customThemeInput}
                  onChange={(event) => setCustomThemeInput(event.target.value)}
                  placeholder={`{\n  "link": "#0f766e",\n  "surface": "#ffffff"\n}`}
                />
                <Paragraph type={customTheme === null ? "danger" : "secondary"}>
                  {customTheme === null
                    ? "JSON 解析失败，仅接受字符串类型 token。"
                    : "支持按 token 局部覆盖内置主题。"}
                </Paragraph>
              </div>

              <Button onClick={() => setCustomThemeInput("")}>
                重置自定义主题
              </Button>
            </Space>
          </Card>
        </Col>

        <Col xs={24} xl={16}>
          <Suspense fallback={<Card loading style={{ minHeight: 620 }} />}>
            <MarkdownRenderer
              content={previewMarkdown}
              themeName={themeName}
              customTheme={customTheme ?? undefined}
              streaming={streaming}
              height={620}
            />
          </Suspense>
        </Col>
      </Row>

      <Card title="选型结论">
        <Table
          pagination={false}
          columns={comparisonColumns}
          dataSource={rendererComparisonRows}
          size="small"
        />
      </Card>
    </Space>
  );
}
