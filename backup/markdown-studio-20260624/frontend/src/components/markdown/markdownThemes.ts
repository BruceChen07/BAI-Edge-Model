import type { CSSProperties } from "react";

export type MarkdownThemeName = "light" | "dark" | "eyeCare";

export type MarkdownThemeTokens = {
  background: string;
  surface: string;
  surfaceElevated: string;
  border: string;
  textPrimary: string;
  textSecondary: string;
  textMuted: string;
  heading: string;
  link: string;
  linkHover: string;
  inlineCodeBg: string;
  inlineCodeText: string;
  codeBg: string;
  codeHeaderBg: string;
  codeBorder: string;
  codeAccent: string;
  quoteBg: string;
  quoteBorder: string;
  success: string;
  warning: string;
  shadow: string;
};

export type MarkdownThemeDefinition = {
  name: MarkdownThemeName;
  label: string;
  description: string;
  mode: "light" | "dark";
  tokens: MarkdownThemeTokens;
};

export type MarkdownThemeOverride = Partial<MarkdownThemeTokens>;

export const BUILTIN_MARKDOWN_THEMES: Record<
  MarkdownThemeName,
  MarkdownThemeDefinition
> = {
  light: {
    name: "light",
    label: "亮色",
    description: "适合日间办公场景，强调清晰层级与高可读性。",
    mode: "light",
    tokens: {
      background: "#f7f9fc",
      surface: "#ffffff",
      surfaceElevated: "#f8fafc",
      border: "#dbe3ef",
      textPrimary: "#14213d",
      textSecondary: "#334155",
      textMuted: "#64748b",
      heading: "#0f172a",
      link: "#2563eb",
      linkHover: "#1d4ed8",
      inlineCodeBg: "#eff6ff",
      inlineCodeText: "#1d4ed8",
      codeBg: "#0f172a",
      codeHeaderBg: "#111827",
      codeBorder: "#1e293b",
      codeAccent: "#60a5fa",
      quoteBg: "#f8fafc",
      quoteBorder: "#93c5fd",
      success: "#10b981",
      warning: "#f59e0b",
      shadow: "0 18px 40px rgba(15, 23, 42, 0.08)",
    },
  },
  dark: {
    name: "dark",
    label: "暗色",
    description: "适合深色桌面环境，提升夜间浏览舒适度。",
    mode: "dark",
    tokens: {
      background: "#020617",
      surface: "#0f172a",
      surfaceElevated: "#111c36",
      border: "#1e293b",
      textPrimary: "#e2e8f0",
      textSecondary: "#cbd5e1",
      textMuted: "#94a3b8",
      heading: "#f8fafc",
      link: "#7dd3fc",
      linkHover: "#38bdf8",
      inlineCodeBg: "#13233f",
      inlineCodeText: "#93c5fd",
      codeBg: "#020617",
      codeHeaderBg: "#111827",
      codeBorder: "#1e293b",
      codeAccent: "#38bdf8",
      quoteBg: "#0b1224",
      quoteBorder: "#38bdf8",
      success: "#34d399",
      warning: "#fbbf24",
      shadow: "0 24px 60px rgba(2, 6, 23, 0.35)",
    },
  },
  eyeCare: {
    name: "eyeCare",
    label: "护眼",
    description: "低对比暖色调，适合长时间阅读与审核。",
    mode: "light",
    tokens: {
      background: "#f4f1e6",
      surface: "#fbf8ef",
      surfaceElevated: "#f6f0df",
      border: "#d8cbb0",
      textPrimary: "#3f3a2b",
      textSecondary: "#5d5747",
      textMuted: "#7c7461",
      heading: "#302a1d",
      link: "#5b7c3c",
      linkHover: "#46612e",
      inlineCodeBg: "#ece6d6",
      inlineCodeText: "#7c4f2f",
      codeBg: "#2f3126",
      codeHeaderBg: "#3d4032",
      codeBorder: "#5b5f4c",
      codeAccent: "#d6c28f",
      quoteBg: "#f2ebd9",
      quoteBorder: "#a58b5e",
      success: "#4d7c0f",
      warning: "#b45309",
      shadow: "0 18px 40px rgba(91, 83, 61, 0.12)",
    },
  },
};

export function resolveMarkdownTheme(
  themeName: MarkdownThemeName,
  override?: MarkdownThemeOverride,
): MarkdownThemeDefinition {
  const base = BUILTIN_MARKDOWN_THEMES[themeName];
  return {
    ...base,
    tokens: {
      ...base.tokens,
      ...override,
    },
  };
}

export function themeTokensToCssVars(
  theme: MarkdownThemeDefinition,
): CSSProperties {
  return {
    "--md-bg": theme.tokens.background,
    "--md-surface": theme.tokens.surface,
    "--md-surface-elevated": theme.tokens.surfaceElevated,
    "--md-border": theme.tokens.border,
    "--md-text-primary": theme.tokens.textPrimary,
    "--md-text-secondary": theme.tokens.textSecondary,
    "--md-text-muted": theme.tokens.textMuted,
    "--md-heading": theme.tokens.heading,
    "--md-link": theme.tokens.link,
    "--md-link-hover": theme.tokens.linkHover,
    "--md-inline-code-bg": theme.tokens.inlineCodeBg,
    "--md-inline-code-text": theme.tokens.inlineCodeText,
    "--md-code-bg": theme.tokens.codeBg,
    "--md-code-header-bg": theme.tokens.codeHeaderBg,
    "--md-code-border": theme.tokens.codeBorder,
    "--md-code-accent": theme.tokens.codeAccent,
    "--md-quote-bg": theme.tokens.quoteBg,
    "--md-quote-border": theme.tokens.quoteBorder,
    "--md-success": theme.tokens.success,
    "--md-warning": theme.tokens.warning,
    "--md-shadow": theme.tokens.shadow,
  } as CSSProperties;
}
