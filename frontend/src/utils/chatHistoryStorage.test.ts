import {
  CHAT_HISTORY_STORAGE_KEY,
  MAX_CHAT_HISTORY_MESSAGES,
  clearChatHistorySnapshot,
  createChatHistoryMessage,
  loadChatHistorySnapshot,
  saveChatHistorySnapshot,
  trimChatHistoryMessages,
} from "./chatHistoryStorage";

describe("chatHistoryStorage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("trims chat history to the latest 10 messages", () => {
    const messages = Array.from({ length: 14 }, (_, index) =>
      createChatHistoryMessage({
        id: `message-${index + 1}`,
        sentAt: `2026-06-23T10:00:${String(index).padStart(2, "0")}.000Z`,
        role: index % 2 === 0 ? "user" : "assistant",
        content: `message-${index + 1}`,
      }),
    );

    const trimmed = trimChatHistoryMessages(messages);

    expect(trimmed).toHaveLength(MAX_CHAT_HISTORY_MESSAGES);
    expect(trimmed[0]?.id).toBe("message-5");
    expect(trimmed.at(-1)?.id).toBe("message-14");
  });

  it("persists and restores a normalized snapshot", () => {
    saveChatHistorySnapshot({
      activeSessionId: "session-1",
      selectedModel: "gemma4:12b",
      selectedKnowledgeBases: ["kb-a"],
      prompt: "draft prompt",
      markdownTheme: "dark",
      messages: Array.from({ length: 12 }, (_, index) =>
        createChatHistoryMessage({
          id: `persist-${index + 1}`,
          sentAt: `2026-06-23T10:00:${String(index).padStart(2, "0")}.000Z`,
          role: index % 2 === 0 ? "user" : "assistant",
          content: `persist-${index + 1}`,
        }),
      ),
    });

    const snapshot = loadChatHistorySnapshot();

    expect(snapshot).not.toBeNull();
    expect(snapshot?.activeSessionId).toBe("session-1");
    expect(snapshot?.selectedModel).toBe("gemma4:12b");
    expect(snapshot?.selectedKnowledgeBases).toEqual(["kb-a"]);
    expect(snapshot?.prompt).toBe("draft prompt");
    expect(snapshot?.markdownTheme).toBe("dark");
    expect(snapshot?.messages).toHaveLength(MAX_CHAT_HISTORY_MESSAGES);
    expect(snapshot?.messages[0]?.id).toBe("persist-3");
  });

  it("returns null for invalid stored JSON", () => {
    window.localStorage.setItem(CHAT_HISTORY_STORAGE_KEY, "{bad-json");

    expect(loadChatHistorySnapshot()).toBeNull();
  });

  it("clears persisted chat history", () => {
    saveChatHistorySnapshot({
      activeSessionId: "session-2",
      selectedKnowledgeBases: [],
      prompt: "",
      markdownTheme: "light",
      messages: [],
    });

    clearChatHistorySnapshot();

    expect(window.localStorage.getItem(CHAT_HISTORY_STORAGE_KEY)).toBeNull();
  });
});
