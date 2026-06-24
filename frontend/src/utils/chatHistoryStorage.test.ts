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
      pendingAttachments: [
        {
          id: "pending-1",
          session_id: "session-1",
          file_name: "pending.txt",
          file_ext: ".txt",
          mime_type: "text/plain",
          file_size: 12,
          attachment_type: "document",
          storage_path: "storage/pending.txt",
          status: "uploaded",
        },
      ],
      messages: Array.from({ length: 12 }, (_, index) =>
        createChatHistoryMessage({
          id: `persist-${index + 1}`,
          sentAt: `2026-06-23T10:00:${String(index).padStart(2, "0")}.000Z`,
          role: index % 2 === 0 ? "user" : "assistant",
          content: `persist-${index + 1}`,
          attachments:
            index === 11
              ? [
                  {
                    id: "linked-1",
                    session_id: "session-1",
                    message_id: "persist-12",
                    file_name: "linked.pdf",
                    file_ext: ".pdf",
                    mime_type: "application/pdf",
                    file_size: 1024,
                    attachment_type: "document",
                    storage_path: "storage/linked.pdf",
                    status: "linked",
                  },
                ]
              : [],
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
    expect(snapshot?.pendingAttachments).toHaveLength(1);
    expect(snapshot?.pendingAttachments[0]?.file_name).toBe("pending.txt");
    expect(snapshot?.messages).toHaveLength(MAX_CHAT_HISTORY_MESSAGES);
    expect(snapshot?.messages[0]?.id).toBe("persist-3");
    expect(snapshot?.messages.at(-1)?.attachments?.[0]?.file_name).toBe(
      "linked.pdf",
    );
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
      pendingAttachments: [],
      messages: [],
    });

    clearChatHistorySnapshot();

    expect(window.localStorage.getItem(CHAT_HISTORY_STORAGE_KEY)).toBeNull();
  });
});
