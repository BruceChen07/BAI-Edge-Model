# Markdown Rendering Optimization — Development Log

**Project**: BAI-Edge-Model / Frontend Markdown Rendering  
**Repository**: https://github.com/BruceChen07/BAI-Edge-Model  
**Plan**: `docs/markdown_rendering_optimization_plan.md`

---

## Phase 1: Design & Prototype
**Start: 2026-06-23 | Status: Completed**

### Daily Progress

| Date | Tasks Completed | Files Changed | Tests (Pass/Fail) | Status |
|------|-----------------|---------------|-------------------|--------|
| 06-23 | 现状梳理：确认聊天页仅支持纯文本 `pre-wrap`，无 Markdown AST 渲染 | `frontend/src/pages/ChatPage.tsx` (analysis) | — | Completed |
| 06-23 | 选型调研：整理 `react-markdown` / `markdown-it` / `marked` 对比与许可证结论 | `docs/markdown_rendering_optimization_plan.md` | — | Completed |
| 06-23 | 高保真原型页设计与实现：支持主题切换、长文本压测、自定义主题 JSON | `frontend/src/pages/MarkdownStudioPage.tsx` | build ok | Completed |

---

## Phase 2: Core Component Implementation
**Start: 2026-06-23 | Status: Completed**

### Daily Progress

| Date | Tasks Completed | Files Changed | Tests (Pass/Fail) | Status |
|------|-----------------|---------------|-------------------|--------|
| 06-23 | 主题系统：3 套内置主题 + CSS Variables token 映射 | `frontend/src/components/markdown/markdownThemes.ts` | — | Completed |
| 06-23 | 长文本分块与虚拟滚动判定逻辑 | `frontend/src/components/markdown/markdownUtils.ts` | unit pending | Completed |
| 06-23 | 代码块渲染：语法高亮、行号、复制按钮 | `frontend/src/components/markdown/CodeBlock.tsx` | build ok | Completed |
| 06-23 | Mermaid 渲染：流程图 / 思维导图 + 错误回退 | `frontend/src/components/markdown/MermaidBlock.tsx` | build ok | Completed |
| 06-23 | 主渲染器：GFM、Math、HTML sanitize、虚拟列表、标题锚点 | `frontend/src/components/markdown/MarkdownRenderer.tsx` | unit pending | Completed |
| 06-23 | 聊天页接入 MarkdownRenderer 并增加主题切换 | `frontend/src/pages/ChatPage.tsx` | build ok | Completed |

### Performance Notes

| Item | Observation | Action |
|------|-------------|--------|
| 静态高亮库导致主包偏大 | 首次构建发现主包约 2.4MB | 改为代码高亮动态加载 |
| Markdown 栈首屏耦合 | 聊天首页会直接引入整套渲染依赖 | 将 `MarkdownRenderer` 改为懒加载 |
| 当前结果 | 主包降至约 1.2MB，MarkdownRenderer 独立 chunk | 后续可继续按路由拆分 `MarkdownStudioPage` |

---

## Phase 3: Testing & Verification
**Start: 2026-06-23 | Status: Completed**

### Daily Progress

| Date | Tasks Completed | Files Changed | Tests (Pass/Fail) | Status |
|------|-----------------|---------------|-------------------|--------|
| 06-23 | 引入 Vitest + Testing Library 测试基座 | `frontend/package.json`, `frontend/vitest.config.ts`, `frontend/src/test/setup.ts` | — | Completed |
| 06-23 | 单元测试：Markdown 分块、主题 JSON 解析、虚拟化判定 | `frontend/src/components/markdown/markdownUtils.test.ts` | 4/0 | Completed |
| 06-23 | 组件测试：标题锚点、安全清洗 | `frontend/src/components/markdown/MarkdownRenderer.test.tsx` | 2/0 | Completed |
| 06-23 | 工程验证：`npm test`、`npm run lint`、`npm run build` | — | 3 commands all pass | Completed |

### Open Risks

- 10 万字混合 Markdown 在真机与低端设备上的 `60fps` 仍需专项压测，不应仅凭本地构建与桌面开发机结果做最终承诺
- Mermaid 相关依赖较重，若移动端体验不理想，可进一步做路由级懒加载与图表开关降级

---

## Deliverables

- `docs/markdown_rendering_optimization_plan.md`
- `docs/markdown_rendering_test_report.md`
- `markdown_rendering_devlog.md`
- `frontend/src/components/markdown/*`
- `frontend/src/pages/MarkdownStudioPage.tsx`
