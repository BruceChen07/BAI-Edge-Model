import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ChatPage } from "./ChatPage";
import { api } from "../services/api";

vi.mock("../components/markdown/MarkdownRenderer", () => ({
  MarkdownRenderer: ({ content }: { content: string }) => <div>{content}</div>,
}));

vi.mock("../services/api", () => ({
  API_BASE: "http://127.0.0.1:8000/api/v1",
  api: {
    listKnowledgeBases: vi.fn().mockResolvedValue([]),
    getModels: vi.fn().mockResolvedValue([
      {
        name: "llava:7b",
        size: 1,
        modified_at: "2026-06-24T00:00:00Z",
        digest: "vision",
        supports_multimodal: true,
        supports_file_upload: true,
        supported_upload_types: ["document", "image"],
      },
    ]),
    checkModelResources: vi.fn().mockResolvedValue({
      feasibility: {
        feasible: true,
        warnings: [],
        current_resources: {
          cpu: {
            cpu_percent: 8,
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
        param_size: "7b",
      },
      recommendations: [],
    }),
    getTimeoutInfo: vi.fn().mockResolvedValue({
      model_name: "llava:7b",
      param_size: "7b",
      timeout: { connect: 10, read: 120, write: 120, pool: 10 },
      user_override: false,
    }),
    setTimeoutOverride: vi.fn().mockResolvedValue({
      user_timeout_override_seconds: null,
      message: "ok",
    }),
    getModelRecommendations: vi.fn().mockResolvedValue([]),
    createSession: vi.fn().mockResolvedValue({
      id: "sess-upload",
      title: "Chat",
      mode: "chat",
      language: "zh-CN",
      rag_enabled: true,
      agent_enabled: false,
    }),
    chat: vi.fn().mockResolvedValue({
      answer: "assistant reply",
      citations: [],
      model_used: "llava:7b",
    }),
    uploadChatAttachment: vi.fn().mockResolvedValue({
      id: "att-1",
      session_id: "sess-upload",
      file_name: "note.txt",
      file_ext: ".txt",
      mime_type: "text/plain",
      file_size: 12,
      attachment_type: "document",
      storage_path: "storage/note.txt",
      extracted_text_preview: "preview",
      ocr_status: "done",
      status: "uploaded",
    }),
    deleteChatAttachment: vi.fn().mockResolvedValue({
      deleted: true,
      attachment_id: "att-1",
    }),
    createKnowledgeBase: vi.fn(),
    uploadKnowledgeBaseFile: vi.fn(),
  },
}));

describe("ChatPage attachments", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  it("uploads chat attachments and sends attachment_ids with the chat request", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    const user = userEvent.setup();

    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <ChatPage locale="zh-CN" />
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("上传聊天附件")).toBeInTheDocument();
      expect(screen.getByTitle("llava:7b")).toBeInTheDocument();
    });

    const fileInput = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement | null;
    expect(fileInput).not.toBeNull();

    fireEvent.change(fileInput!, {
      target: {
        files: [
          new File(["hello world"], "note.txt", {
            type: "text/plain",
          }),
        ],
      },
    });

    await waitFor(() => {
      expect(screen.getByText("note.txt")).toBeInTheDocument();
      expect(api.uploadChatAttachment).toHaveBeenCalledTimes(1);
    });

    await user.type(
      screen.getByPlaceholderText("输入你的问题，直接和本地大模型对话..."),
      "Please use the attached note",
    );
    await user.click(screen.getByRole("button", { name: /发\s*送/ }));

    await waitFor(() => {
      expect(api.chat).toHaveBeenCalledWith(
        expect.objectContaining({
          session_id: "sess-upload",
          query: "Please use the attached note",
          model_name: "llava:7b",
          attachment_ids: ["att-1"],
        }),
      );
    });

    await waitFor(() => {
      expect(screen.getByText("assistant reply")).toBeInTheDocument();
      expect(screen.getByText("下载附件")).toBeInTheDocument();
    });
  });
});
