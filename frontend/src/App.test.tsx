import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "./App";

vi.mock("./pages/ChatPage", () => ({
  ChatPage: () => <div>chat-page</div>,
}));

vi.mock("./pages/AdminPage", () => ({
  AdminPage: () => <div>admin-page</div>,
}));

vi.mock("./pages/KnowledgeBaseManagePage", () => ({
  KnowledgeBaseManagePage: () => <div>knowledge-base-page</div>,
}));

vi.mock("./pages/ModelCatalogPage", () => ({
  ModelCatalogPage: () => <div>catalog-page</div>,
}));

vi.mock("./pages/DownloadPage", () => ({
  DownloadPage: () => <div>download-page</div>,
}));

function renderApp(initialEntries: string[] = ["/"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <App />
    </MemoryRouter>,
  );
}

describe("App navigation", () => {
  it("removes the markdown studio navigation entry and keeps core navigation working", async () => {
    const user = userEvent.setup();
    renderApp();

    expect(screen.queryByRole("button", { name: "Markdown 工作室" })).not.toBeInTheDocument();
    expect(screen.getByText("chat-page")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "管理后台" }));
    expect(screen.getByText("admin-page")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "模型目录" }));
    expect(screen.getByText("catalog-page")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "下载中心" }));
    expect(screen.getByText("download-page")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "知识库管理" }));
    expect(screen.getByText("knowledge-base-page")).toBeInTheDocument();
  });

  it("redirects the removed markdown studio route back to the home page", () => {
    renderApp(["/markdown-studio"]);

    expect(screen.getByText("chat-page")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Markdown 工作室" })).not.toBeInTheDocument();
  });
});
