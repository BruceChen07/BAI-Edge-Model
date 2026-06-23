# 大模型 Markdown 数据前端渲染优化方案

**项目**: BAI-Edge-Model / Frontend Markdown Rendering  
**创建日期**: 2026-06-23  
**状态**: Phase 1-2 已实现，待内部审核  
**原型入口**: `frontend/src/pages/MarkdownStudioPage.tsx` 对应路由 `/markdown-studio`

---

## 1. 背景与目标

当前聊天页对大模型返回结果仅做纯文本 `pre-wrap` 展示，无法满足以下场景需求：

- 代码块缺乏语法高亮、行号与复制能力
- LaTeX 公式、Mermaid 流程图/思维导图无法直观展示
- 表格在窄屏和长文本场景下可读性差
- 大篇幅 Markdown 在聊天场景中容易造成首屏阻塞和滚动卡顿
- 原生 HTML 嵌入缺乏安全边界，存在 XSS 风险
- 缺少统一主题系统，无法支撑亮色 / 暗色 / 护眼模式及自定义主题扩展

本方案的目标是在不改变现有会话与推理接口的前提下，为大模型回答增加一套可复用、可配置、可测试、可审计的 Markdown 渲染能力。

---

## 2. 现状分析

### 2.1 当前返回字段结构

基于现有前后端链路，聊天响应主字段如下：

```json
{
  "data": {
    "answer": "LLM answer content, may include markdown",
    "citations": [
      {
        "file_name": "kb.docx",
        "score": 0.82
      }
    ],
    "model_used": "qwen3:8b"
  }
}
```

前端当前使用方式：

- `response.answer` -> 直接作为聊天消息正文
- `response.citations` -> 单独渲染引用卡片
- `response.model_used` -> Tag 展示

### 2.2 当前渲染缺口

- 聊天正文在 [ChatPage.tsx](file:///d:/Workspace/BAI-Edge-Model/frontend/src/pages/ChatPage.tsx) 中仅以 `Paragraph + whiteSpace: "pre-wrap"` 呈现
- 未引入 Markdown AST 解析、插件扩展或安全清洗能力
- 未建立任何主题 token、长文本分块或可视化原型页

---

## 3. 复杂语法兼容性评估

| 语法类型 | 大模型常见输出形式 | 兼容性结论 | 实现策略 |
|---|---|---|---|
| 标题 / 段落 / 列表 | `#`、`-`、`1.` | 完全兼容 | `react-markdown + remark-gfm` |
| 表格 | GFM table | 完全兼容 | `remark-gfm` + 横向滚动容器 |
| 引用 / 任务列表 | `>`、`- [x]` | 完全兼容 | `remark-gfm` |
| 代码块 | `````lang` | 完全兼容 | 自定义 `code` renderer + `react-syntax-highlighter` |
| 行内代码 | `` `code` `` | 完全兼容 | 自定义样式 token |
| LaTeX 公式 | `$...$` / `$$...$$` | 完全兼容 | `remark-math + rehype-katex` |
| Mermaid 流程图 | ```mermaid | 完全兼容 | 动态加载 `mermaid` |
| Mermaid 思维导图 | ```mermaid + mindmap | 完全兼容 | 复用 Mermaid |
| Mermaid 变体语法 | ```mindmap / ```flowchart | 兼容 | 语言名归一化为 `mermaid` |
| 原生 HTML | `<details>` `<mark>` `<div>` | 白名单兼容 | `rehype-raw + rehype-sanitize` |
| 脚本 / 危险属性 | `<script>` / `onerror=` | 拦截 | 清洗白名单 |
| 超长文档 | 10 万字以上 | 需专项优化 | 分块解析 + 虚拟滚动 |

结论：

- 复杂语法能力可以通过 `unified` 生态完整覆盖
- Mermaid 与 KaTeX 均建议按需懒加载或分离渲染，避免常规回答承担全部首包开销
- 原生 HTML 仅允许白名单标签，不允许脚本与危险事件属性

---

## 4. 前端渲染框架选型论证

### 4.1 候选库对比

| 维度 | react-markdown | markdown-it | marked |
|---|---|---|---|
| 功能完整性 | 高，天然适合 React 组件化渲染 | 高，语法解析性能优秀 | 中，核心轻量但高级能力需手动拼装 |
| React 集成 | 极佳，直接输出 React 节点 | 一般，常见模式为 HTML 字符串 -> DOM | 一般，常见模式为 HTML 字符串 -> DOM |
| AST / 插件生态 | 极强，remark / rehype 完整 | 强，插件多，但与 React 组件桥接成本较高 | 中，扩展生态偏底层 |
| 安全默认值 | 相对安全，不依赖 `dangerouslySetInnerHTML` | 可安全，但通常需要额外 sanitizer | 默认不做 sanitize，必须额外处理 |
| Mermaid / Math 集成 | 成熟，组合式插件与自定义 renderer 容易 | 可实现，但链路更分散 | 可实现，但更偏手工拼装 |
| 包体积 | 中等 | 中等偏高 | 较低 |
| 性能 | 中高 | 高 | 高 |
| 维护活跃度 | 高 | 高 | 高 |
| 适合本项目 | 最优 | 备选 | 不作为主选 |

### 4.2 选型数据快照

以下数据基于 2026-06-23 对 npm / GitHub / Bundlephobia 的快照整理：

| 库 | 版本 | License | GitHub Stars | 最近活跃信号 | 依赖数 | Bundle 参考 |
|---|---|---|---|---|---|---|
| react-markdown | 10.1.0 | MIT | ~14k | 2025-03 发布 10.1.0，2026 仍活跃 | 11 | min+gzip ~33.3kB |
| markdown-it | 14.2.0 | MIT | ~21k | GitHub 2026-03 仍有更新 | 6 | min+gzip ~54kB |
| marked | 18.0.x | MIT | ~36k | 2026-03 仍有版本与修复 | 0 | npm 强调 built for speed |

### 4.3 选型结论

主选：

- `react-markdown` 作为主渲染框架
- 原因：最适合 React 19 + Vite + Ant Design 技术栈，插件生态完整，便于将代码块、Mermaid、表格、主题系统、安全策略统一收口到组件层

备选：

- `markdown-it` 适合需要极致解析性能、且更偏 HTML 输出的场景

不推荐作为本项目主方案：

- `marked` 本身性能优秀，但安全与组件化能力更多依赖二次拼装，整体工程复杂度更高

---

## 5. 技术栈与依赖清单

### 5.1 本次实施使用的依赖

| 组件 | 用途 | License |
|---|---|---|
| `react-markdown` | React Markdown 主渲染器 | MIT |
| `remark-gfm` | GFM 语法，表格/任务列表/删除线 | MIT |
| `remark-math` | 数学公式语法解析 | MIT |
| `rehype-katex` | KaTeX 公式渲染 | MIT |
| `katex` | 公式样式与渲染基础 | MIT |
| `rehype-raw` | 解析 Markdown 中白名单 HTML | MIT |
| `rehype-sanitize` | XSS 清洗 | MIT |
| `mermaid` | 流程图 / 思维导图渲染 | MIT |
| `react-syntax-highlighter` | 代码高亮与行号显示 | MIT |
| `@tanstack/react-virtual` | 虚拟滚动 | MIT |
| `vitest` | 单元测试 | MIT |
| `@testing-library/react` | React 组件测试 | MIT |

### 5.2 许可证合规结论

- 本次新增依赖均为宽松开源许可证，适合企业内部与商业项目使用
- 未引入 GPL / AGPL / SSPL 等高约束许可证组件
- Mermaid / KaTeX / unified 生态依赖需在发版清单中保留 LICENSE 文件归档
- 上线前建议通过 SBOM 或 `license-checker` 再做一次 CI 级别核验

---

## 6. 主题系统设计

### 6.1 主题目标

- 提供 3 套内置主题：亮色、暗色、护眼
- 支持运行时动态切换
- 支持通过 JSON token 覆盖局部样式，实现自定义主题
- 保持代码块、表格、引用块、链接、标题在不同主题下的视觉一致性

### 6.2 Token 设计

核心 token：

- `background`
- `surface`
- `surfaceElevated`
- `border`
- `textPrimary`
- `textSecondary`
- `textMuted`
- `heading`
- `link`
- `inlineCodeBg`
- `inlineCodeText`
- `codeBg`
- `codeHeaderBg`
- `quoteBg`
- `quoteBorder`

### 6.3 内置主题定义

- `light`: 适合日间办公，强调清晰层级
- `dark`: 适合夜间环境，减轻高亮刺激
- `eyeCare`: 暖色低对比，适合长时间阅读与审阅

### 6.4 动态切换方案

- 通过 `MarkdownRenderer` 传入 `themeName`
- 组件内部将 token 映射为 CSS Variables
- 样式层通过 `var(--md-*)` 统一消费，降低主题切换成本

### 6.5 自定义主题配置

- 审核原型页支持 JSON 覆盖 token
- 产品化阶段建议补齐“导入/导出主题配置”“主题预设分享”“主题持久化存储”

---

## 7. 复杂语法渲染实现方案

### 7.1 代码块

能力要求：

- 语法高亮
- 行号显示
- 一键复制
- 长行换行
- 语言标识

实现方案：

- 通过自定义 `code` renderer 拦截 fenced code block
- 普通代码块使用 `react-syntax-highlighter`
- `showLineNumbers` 打开行号
- toolbar 提供 `Copy` 操作

### 7.2 LaTeX 数学公式

实现方案：

- `remark-math` 解析语法节点
- `rehype-katex` 输出公式 HTML
- `katex.min.css` 在 `main.tsx` 全局引入

### 7.3 Mermaid 流程图 / 思维导图

实现方案：

- 将 ````mermaid`、```mindmap`、```flowchart` 统一识别为 Mermaid
- `MermaidBlock` 组件内动态加载 `mermaid`
- 设置 `securityLevel: "strict"`，避免不安全脚本
- 渲染失败时回退到原始文本 + 错误提示

### 7.4 表格响应式

实现方案：

- 外层套 `markdown-table-scroll`
- 设置 `overflow-x: auto`
- 通过最小宽度保留表头和单元格可读性

---

## 8. 性能优化方案

### 8.1 问题定义

大模型流式输出常见问题：

- 10 万字长文本首次渲染阻塞主线程
- Mermaid / KaTeX / 代码高亮在整篇文档一起渲染时造成卡顿
- 聊天容器与 Markdown 内容双层滚动时，布局计算成本高

### 8.2 设计策略

1. 分块解析
- 将 Markdown 按段落、代码块、公式块、表格块切分为 section
- 保证 fenced code / math / table 不被错误拆断

2. 分片渲染
- 在流式模式下逐帧追加 section，而不是一次性创建全部节点

3. 虚拟滚动
- 对 section 列表使用 `@tanstack/react-virtual`
- 只挂载可视区域 + overscan 节点

4. 重对象懒加载
- Mermaid 在需要时动态 `import`

### 8.3 当前实现状态

- 已实现 section 切分
- 已实现长文本虚拟滚动
- 已实现流式递增渲染
- 已提供 `/markdown-studio` 长文本压测模式

### 8.4 上线前专项性能压测要求

- 使用 10 万字混合 Markdown（代码、公式、Mermaid、表格）作为基准数据集
- 在 Chrome Performance 中记录：
  - FPS
  - scripting time
  - layout time
  - long task 数量
- 目标：
  - 首屏渲染不出现连续 > 100ms long task
  - 滚动保持流畅
  - 聊天页切换主题时无明显卡顿

备注：

- `60fps` 为目标值，正式验收需基于真实设备矩阵测试，不宜仅凭本地开发机声明完全达标

---

## 9. 安全防护方案

### 9.1 风险

- Markdown 内植入 `<script>`、`onerror=`、`javascript:` 链接
- 不可信 HTML 导致 DOM 注入
- Mermaid 或第三方图形库在宽松模式下执行不安全内容

### 9.2 实施策略

- `rehype-raw` 只负责解析 HTML，不直接放行
- `rehype-sanitize` 按白名单清洗标签与属性
- 禁止脚本标签与事件属性
- Mermaid 使用 `securityLevel: "strict"`
- 链接统一加 `target="_blank"` 与 `rel="noreferrer noopener"`

### 9.3 合法 HTML 保留边界

当前允许的合法 HTML 重点覆盖：

- `div`
- `span`
- `details`
- `summary`
- `mark`
- `sup`
- `sub`
- `kbd`
- `img`

如后续业务需要 `iframe` / `video` 等嵌入能力，应增加来源域名 allowlist，不建议直接全放开。

---

## 10. 组件架构设计

```
ChatPage / MarkdownStudioPage
        │
        ▼
MarkdownRenderer
 ├─ markdownThemes.ts
 ├─ markdownUtils.ts
 ├─ CodeBlock.tsx
 ├─ MermaidBlock.tsx
 └─ VirtualizedMarkdown (inner)
```

职责划分：

- `MarkdownRenderer`: 入口、主题、渲染模式切换
- `CodeBlock`: 高亮、行号、复制
- `MermaidBlock`: 图表渲染与错误回退
- `markdownUtils`: 长文本切分、虚拟化判定、主题 JSON 解析
- `MarkdownStudioPage`: 高保真原型与审核演示页

---

## 11. 开发周期拆解

### Phase 1: 方案设计与原型

工期：1 人日

- 字段结构梳理
- 库选型对比
- 主题与安全策略设计
- 原型页设计与审核演示入口

### Phase 2: 核心组件开发

工期：1.5 人日

- MarkdownRenderer
- CodeBlock
- MermaidBlock
- Theme Tokens
- ChatPage 接入

### Phase 3: 性能与测试

工期：1 人日

- 虚拟滚动
- 分片渲染
- 单元测试
- 构建 / lint / 兼容性检查

### Phase 4: 上线准备

工期：0.5 人日

- 使用文档
- 二次开发指南
- 问题排查手册
- 许可证与安全审计

总预估：4 人日

---

## 12. 人员分工建议

| 角色 | 责任 |
|---|---|
| 前端开发 A | 核心渲染组件、主题系统、聊天页接入 |
| 前端开发 B | 原型页、性能优化、兼容性修正 |
| QA | 语法兼容、跨浏览器、移动端验收 |
| 安全 / 架构评审 | XSS、许可证、上线门禁审查 |
| 产品 / 设计 | 审核主题视觉与交互细节 |

若单人开发，则按 `方案 -> 组件 -> 测试 -> 文档` 顺序执行。

---

## 13. 测试节点

### 13.1 单元测试

- Markdown 分块逻辑
- 主题自定义配置解析
- 安全清洗行为
- 标题锚点渲染

### 13.2 集成测试

- 聊天页渲染包含 Markdown 的模型回答
- 原型页切换主题与长文本模式
- 代码块复制、Mermaid、公式联动展示

### 13.3 性能测试

- 10 万字长文本渲染
- 流式追加渲染
- 虚拟滚动稳定性

### 13.4 兼容性测试

桌面端：

- Chrome
- Edge
- Firefox
- Safari

移动端：

- 微信内置浏览器
- 支付宝内置浏览器
- 华为 / 小米 / OPPO / vivo 自带浏览器

---

## 14. 上线前检查清单

- [ ] UI 审核通过（以 `/markdown-studio` 为验收页）
- [ ] 单元测试通过
- [ ] 构建通过
- [ ] 安全审计通过
- [ ] 许可证清单归档
- [ ] 10 万字性能压测记录归档
- [ ] 使用文档 / 二开指南 / 排障手册完成

---

## 15. 本次实现交付物

- `frontend/src/components/markdown/MarkdownRenderer.tsx`
- `frontend/src/components/markdown/CodeBlock.tsx`
- `frontend/src/components/markdown/MermaidBlock.tsx`
- `frontend/src/components/markdown/markdownThemes.ts`
- `frontend/src/components/markdown/markdownUtils.ts`
- `frontend/src/components/markdown/markdown.css`
- `frontend/src/pages/MarkdownStudioPage.tsx`
- `frontend/src/pages/ChatPage.tsx`
- `frontend/src/components/markdown/*.test.ts(x)`
- `docs/markdown_rendering_optimization_plan.md`

---

## 16. 审核结论建议

建议以“原型页 + 聊天页真实接入 + 测试报告”三项联合进入内部审核：

1. 审核视觉与交互：访问 `/markdown-studio`
2. 审核真实业务接入：访问聊天首页 `/`
3. 审核工程质量：查看测试报告与开发日志

若审核通过，可进入下一步：

- 增量流式接口联动优化
- 自定义主题持久化
- 真机矩阵性能压测与移动端适配
