import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";

import { ChatPage } from "./ChatPage";
import { CHAT_HISTORY_STORAGE_KEY } from "../utils/chatHistoryStorage";

vi.mock("../components/markdown/MarkdownRenderer", () => ({
  MarkdownRenderer: ({ content }: { content: string }) => <div>{content}</div>,
}));

vi.mock("../services/api", () => ({
  api: {
    listKnowledgeBases: vi.fn().mockResolvedValue([]),
    getModels: vi.fn().mockResolvedValue([
      {
        name: "gemma4:12b",
        size: 1,
        modified_at: "2026-06-23T00:00:00Z",
        digest: "digest",
      },
    ]),
    checkModelResources: vi.fn().mockResolvedValue({
      feasibility: {
        feasible: true,
        warnings: [],
        current_resources: {
          cpu: {
            cpu_percent: 10,
            cpu_cores_physical: 4,
            cpu_cores_logical: 8,
          },
          memory: {
            total_gb: 16,
            available_gb: 8,
            used_gb: 8,
            percent: 50,
            swap_total_gb: 0,
            swap_used_gb: 0,
          },
          gpu: { available: false },
        },
        model_requirement: null,
        recommendation: null,
        param_size: "12b",
      },
      recommendations: [],
    }),
    getTimeoutInfo: vi.fn().mockResolvedValue({
      model_name: "gemma4:12b",
      param_size: "12b",
      timeout: { connect: 10, read: 120, write: 120, pool: 10 },
      user_override: false,
    }),
    setTimeoutOverride: vi.fn().mockResolvedValue({
      user_timeout_override_seconds: null,
      message: "ok",
    }),
    getModelRecommendations: vi.fn().mockResolvedValue([]),
    createSession: vi.fn(),
    chat: vi.fn(),
    createKnowledgeBase: vi.fn(),
    uploadKnowledgeBaseFile: vi.fn(),
  },
}));

describe("ChatPage history restore", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem(
      CHAT_HISTORY_STORAGE_KEY,
      JSON.stringify({
        version: 1,
        updatedAt: "2026-06-23T10:00:00.000Z",
        activeSessionId: "session-keep",
        selectedModel: "gemma4:12b",
        selectedKnowledgeBases: ["kb-1"],
        prompt: "follow-up question",
        markdownTheme: "dark",
        messages: [
          {
            id: "message-user",
            sentAt: "2026-06-23T10:00:01.000Z",
            role: "user",
            content: "历史用户消息",
            modelName: "gemma4:12b",
          },
          {
            id: "message-assistant",
            sentAt: "2026-06-23T10:00:02.000Z",
            role: "assistant",
            content: "历史助手消息",
            modelName: "gemma4:12b",
          },
        ],
      }),
    );
  });

  it("loads chat history from localStorage on initialization", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ChatPage locale="zh-CN" />
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("历史用户消息")).toBeInTheDocument();
      expect(screen.getByText("历史助手消息")).toBeInTheDocument();
    });

    expect(screen.getByDisplayValue("follow-up question")).toBeInTheDocument();
    expect(screen.getByTitle("gemma4:12b")).toBeInTheDocument();
  });
});
