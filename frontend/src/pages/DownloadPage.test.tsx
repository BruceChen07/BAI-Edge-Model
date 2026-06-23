import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { DownloadPage } from "./DownloadPage";
import { api } from "../services/api";

vi.mock("../services/api", () => ({
  api: {
    listDownloadJobs: vi.fn(),
    getDownloadJob: vi.fn(),
    getDownloadPlan: vi.fn(),
    pullModelMultiSource: vi.fn(),
    pauseDownloadJob: vi.fn(),
  },
}));

class MockEventSource {
  static instances: MockEventSource[] = [];

  url: string;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  close(): void {
    // no-op
  }

  emit(payload: unknown): void {
    this.onmessage?.({
      data: JSON.stringify(payload),
    } as MessageEvent<string>);
  }
}

const mockedApi = vi.mocked(api);

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <DownloadPage locale="zh-CN" />
    </QueryClientProvider>,
  );
}

describe("DownloadPage", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);

    mockedApi.getDownloadPlan.mockResolvedValue({
      model_name: "qwen3:8b",
      sources: [{ name: "modelscope", url: "https://example.com", priority: 1, enabled: true, timeout_seconds: 60 }],
    });
    mockedApi.pauseDownloadJob.mockResolvedValue({
      message: "paused",
      job_id: "job-1",
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("loads job detail and subscribes progress by job id after starting a download", async () => {
    const user = userEvent.setup();
    mockedApi.listDownloadJobs
      .mockResolvedValueOnce({ total: 0, items: [] })
      .mockResolvedValue({
        total: 1,
        items: [
          {
            id: "job-1",
            model_name: "qwen3:8b",
            source_name: "modelscope",
            source_url: "https://example.com/model.gguf",
            total_bytes: 100,
            downloaded_bytes: 40,
            chunk_size: 1048576,
            status: "downloading",
            error_message: "",
            retry_count: 0,
            max_retries: 3,
            priority: 2,
            output_path: "D:/models/qwen3_8b.gguf",
            started_at: "2026-06-24T00:00:00Z",
            completed_at: "",
            last_progress_at: "2026-06-24T00:00:10Z",
            created_at: "2026-06-24T00:00:00Z",
            updated_at: "2026-06-24T00:00:10Z",
          },
        ],
      });
    mockedApi.getDownloadJob.mockResolvedValue({
      id: "job-1",
      model_name: "qwen3:8b",
      source_name: "modelscope",
      source_url: "https://example.com/model.gguf",
      total_bytes: 100,
      downloaded_bytes: 40,
      chunk_size: 1048576,
      status: "downloading",
      error_message: "",
      retry_count: 0,
      max_retries: 3,
      priority: 2,
      output_path: "D:/models/qwen3_8b.gguf",
      started_at: "2026-06-24T00:00:00Z",
      completed_at: "",
      last_progress_at: "2026-06-24T00:00:10Z",
      created_at: "2026-06-24T00:00:00Z",
      updated_at: "2026-06-24T00:00:10Z",
    });
    mockedApi.pullModelMultiSource.mockResolvedValue({
      model_name: "qwen3:8b",
      status: "accepted",
      source: "modelscope",
      job_id: "job-1",
      error: "",
      elapsed_seconds: 0,
    });

    renderPage();

    await user.click(screen.getByRole("button", { name: "开始下载" }));

    await waitFor(() => {
      expect(mockedApi.pullModelMultiSource).toHaveBeenCalled();
      expect(mockedApi.getDownloadJob).toHaveBeenCalledWith("job-1");
    });

    await waitFor(() => {
      expect(MockEventSource.instances.at(-1)?.url).toContain(
        "/api/v1/download/jobs/job-1/progress",
      );
    });

    await waitFor(() => {
      expect(screen.getByText("D:/models/qwen3_8b.gguf")).toBeInTheDocument();
    });

    act(() => {
      MockEventSource.instances.at(-1)?.emit({
        job_id: "job-1",
        model_name: "qwen3:8b",
        status: "downloading",
        downloaded_bytes: 50,
        total_bytes: 100,
        percent: 50,
        speed_mbps: 2,
        eta_seconds: 10,
        source_name: "modelscope",
        error: "",
      });
    });

    await waitFor(() => {
      expect(screen.getByText(/50%/)).toBeInTheDocument();
      expect(screen.getByText(/2 MB\/s/)).toBeInTheDocument();
    });
  });

  it("shows backend error details for the selected job", async () => {
    mockedApi.listDownloadJobs.mockResolvedValue({
      total: 1,
      items: [
        {
          id: "job-failed",
          model_name: "qwen3:8b",
          source_name: "ollama",
          source_url: "",
          total_bytes: 0,
          downloaded_bytes: 0,
          chunk_size: 1048576,
          status: "failed",
          error_message: "disk full",
          retry_count: 1,
          max_retries: 3,
          priority: 2,
          output_path: "D:/models/qwen3_8b.gguf",
          started_at: "2026-06-24T00:00:00Z",
          completed_at: "2026-06-24T00:00:05Z",
          last_progress_at: "2026-06-24T00:00:05Z",
          created_at: "2026-06-24T00:00:00Z",
          updated_at: "2026-06-24T00:00:05Z",
        },
      ],
    });
    mockedApi.getDownloadJob.mockResolvedValue({
      id: "job-failed",
      model_name: "qwen3:8b",
      source_name: "ollama",
      source_url: "",
      total_bytes: 0,
      downloaded_bytes: 0,
      chunk_size: 1048576,
      status: "failed",
      error_message: "disk full",
      retry_count: 1,
      max_retries: 3,
      priority: 2,
      output_path: "D:/models/qwen3_8b.gguf",
      started_at: "2026-06-24T00:00:00Z",
      completed_at: "2026-06-24T00:00:05Z",
      last_progress_at: "2026-06-24T00:00:05Z",
      created_at: "2026-06-24T00:00:00Z",
      updated_at: "2026-06-24T00:00:05Z",
    });
    mockedApi.pullModelMultiSource.mockResolvedValue({
      model_name: "qwen3:8b",
      status: "accepted",
      source: "ollama",
      job_id: "job-failed",
      error: "",
      elapsed_seconds: 0,
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/错误信息: disk full/)).toBeInTheDocument();
    });
  });
});
