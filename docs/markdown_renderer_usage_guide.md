# Markdown Renderer 使用文档 / 二次开发指南 / 排查手册

**Project**: BAI-Edge-Model  
**Component**: Frontend Markdown Renderer

---

## 1. 组件概述

主组件：

- `frontend/src/components/markdown/MarkdownRenderer.tsx`

配套模块：

- `CodeBlock.tsx`
- `MermaidBlock.tsx`
- `markdownThemes.ts`
- `markdownUtils.ts`
- `markdown.css`

典型使用场景：

- 聊天回答渲染
- 审核演示页 / 文档页
- 报告中心 / 知识检索结果页

---

## 2. 快速接入

### 2.1 基础用法

```tsx
import { MarkdownRenderer } from "../components/markdown/MarkdownRenderer";

<MarkdownRenderer
  content={answer}
  themeName="light"
/>
```

### 2.2 聊天页懒加载接入

```tsx
const MarkdownRenderer = lazy(async () => ({
  default: (await import("../components/markdown/MarkdownRenderer"))
    .MarkdownRenderer,
}));
```

适用场景：

- 首屏尽量减少 Markdown 栈对主包的影响
- 仅在存在模型回答时再加载渲染能力

### 2.3 长文本模式

```tsx
<MarkdownRenderer
  content={longMarkdown}
  themeName="eyeCare"
  streaming
  height={620}
/>
```

---

## 3. Props 说明

| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `content` | `string` | 必填 | Markdown 原文 |
| `themeName` | `"light" \| "dark" \| "eyeCare"` | `light` | 内置主题 |
| `customTheme` | `Partial<MarkdownThemeTokens>` | `undefined` | 覆盖内置 token |
| `className` | `string` | `undefined` | 外层额外 class |
| `style` | `CSSProperties` | `undefined` | 外层内联样式 |
| `enableHtml` | `boolean` | `true` | 是否启用白名单 HTML |
| `enableVirtualization` | `boolean` | `true` | 是否允许长文本虚拟滚动 |
| `streaming` | `boolean` | `false` | 是否启用增量渲染 |
| `height` | `number` | `520` | 虚拟滚动容器高度 |

---

## 4. 主题扩展

### 4.1 内置主题

- `light`
- `dark`
- `eyeCare`

### 4.2 自定义主题

```tsx
<MarkdownRenderer
  content={markdown}
  themeName="light"
  customTheme={{
    link: "#0f766e",
    surface: "#ffffff",
    border: "#cbd5e1",
  }}
/>
```

### 4.3 新增主题流程

1. 在 `markdownThemes.ts` 中增加主题 definition
2. 为 `MarkdownThemeName` 联合类型补充新值
3. 在页面主题切换控件中加入新选项
4. 补充主题截图和验收说明

---

## 5. 二次开发指南

### 5.1 新增 Markdown 语法支持

推荐顺序：

1. 判断是否已有 `remark` / `rehype` 插件
2. 若语法需要自定义组件，优先在 `components` map 中扩展
3. 若语法具备高计算成本，优先考虑懒加载

示例：

- admonition / callout
- TOC
- footnote
- 自定义 code fence 语法

### 5.2 新增受控 HTML 白名单

入口位置：

- `MarkdownRenderer.tsx` -> `markdownSanitizeSchema`

原则：

- 仅放行明确需要的标签和属性
- 不接受事件属性
- 如需放行 `iframe`，必须同时增加 host allowlist

### 5.3 自定义代码块渲染

入口位置：

- `CodeBlock.tsx`

可扩展能力：

- 语言别名映射
- 代码折叠
- 下载代码文件
- 差异高亮

### 5.4 自定义 Mermaid 能力

入口位置：

- `MermaidBlock.tsx`

可扩展项：

- 主题映射
- 渲染超时控制
- 导出 SVG / PNG
- 图表开关降级

---

## 6. 常见问题排查

### 6.1 没有渲染成 Markdown，只显示原文

排查步骤：

1. 确认 `content` 是否确实包含 Markdown
2. 确认页面是否使用 `MarkdownRenderer` 而非普通 `Paragraph`
3. 确认懒加载组件是否被 `Suspense` 正常包裹

### 6.2 公式不显示

排查步骤：

1. 检查 `main.tsx` 是否引入 `katex/dist/katex.min.css`
2. 确认输入格式为 `$...$` 或 `$$...$$`
3. 确认 `remark-math`、`rehype-katex` 依赖存在

### 6.3 Mermaid 图表不显示

排查步骤：

1. 检查代码块语言名是否为 `mermaid` / `mindmap` / `flowchart`
2. 打开控制台确认 Mermaid 是否报语法错误
3. 查看 `MermaidBlock` 是否进入 error fallback

### 6.4 HTML 被过滤

原因：

- 当前只允许白名单标签与属性

排查步骤：

1. 查看 `markdownSanitizeSchema`
2. 判断是否真的是业务必要标签
3. 若需新增标签，先做安全评审再放开

### 6.5 长文本仍然卡顿

排查步骤：

1. 确认 `enableVirtualization` 未关闭
2. 确认输入内容已超过虚拟化阈值
3. 观察是否是 Mermaid / 代码块过多导致的单块计算过重
4. 使用 Chrome Performance 记录 long task

### 6.6 构建后包体偏大

排查步骤：

1. 确认 `MarkdownRenderer` 是否仍被静态引入到首屏
2. 确认高亮库是否再次被同步 import
3. 评估是否需要将 `MarkdownStudioPage` 路由进一步拆分

---

## 7. 推荐验收流程

1. 打开 `/markdown-studio` 检查：
   - 三套主题
   - 代码高亮
   - KaTeX
   - Mermaid 流程图与思维导图
   - 自定义主题 JSON
   - 长文本模式
2. 打开聊天首页 `/`，发送带 Markdown 的问题，确认真实链路展示正常
3. 运行：

```bash
npm test
npm run lint
npm run build
```

---

## 8. 后续建议

- 增加流式接口逐 token 渲染联动
- 增加主题持久化
- 引入真实设备压测脚本
- 建立 bundle size CI 门禁
