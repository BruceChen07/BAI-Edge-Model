export const CHAT_HISTORY_STORAGE_KEY = "bai-edge-model.chat-history.v1";
export const MAX_CHAT_HISTORY_MESSAGES = 10;

export type ChatHistoryRole = "user" | "assistant";

export type ChatHistoryAttachment = {
  id: string;
  session_id: string;
  message_id?: string | null;
  file_name: string;
  file_ext: string;
  mime_type: string;
  file_size: number;
  attachment_type: string;
  storage_path: string;
  extracted_text_preview?: string;
  ocr_status?: string;
  status?: string;
  created_at?: string | null;
};

export type ChatHistoryMessage = {
  id: string;
  sentAt: string;
  role: ChatHistoryRole;
  content: string;
  modelName?: string;
  citations?: Array<Record<string, unknown>>;
  attachments?: ChatHistoryAttachment[];
};

export type ChatHistorySnapshot = {
  activeSessionId?: string;
  selectedModel?: string;
  selectedKnowledgeBases: string[];
  prompt: string;
  markdownTheme: "light" | "dark" | "eyeCare";
  pendingAttachments: ChatHistoryAttachment[];
  messages: ChatHistoryMessage[];
};

type PersistedChatHistorySnapshot = {
  version: 1;
  updatedAt: string;
  activeSessionId?: string;
  selectedModel?: string;
  selectedKnowledgeBases?: string[];
  prompt?: string;
  markdownTheme?: "light" | "dark" | "eyeCare";
  pendingAttachments?: ChatHistoryAttachment[];
  messages?: ChatHistoryMessage[];
};

function getStorage(storage?: Storage): Storage | null {
  if (storage) {
    return storage;
  }

  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage;
}

function createMessageId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  return `chat-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function createChatHistoryMessage(
  input: Omit<ChatHistoryMessage, "id" | "sentAt"> & {
    id?: string;
    sentAt?: string;
  },
): ChatHistoryMessage {
  return {
    id: input.id ?? createMessageId(),
    sentAt: input.sentAt ?? new Date().toISOString(),
    role: input.role,
    content: input.content,
    modelName: input.modelName,
    citations: input.citations,
    attachments: input.attachments ?? [],
  };
}

export function trimChatHistoryMessages(
  messages: ChatHistoryMessage[],
  maxCount = MAX_CHAT_HISTORY_MESSAGES,
): ChatHistoryMessage[] {
  if (messages.length <= maxCount) {
    return messages;
  }

  return messages.slice(messages.length - maxCount);
}

export function normalizeChatHistorySnapshot(
  snapshot?: Partial<ChatHistorySnapshot> | null,
): ChatHistorySnapshot {
  return {
    activeSessionId: snapshot?.activeSessionId,
    selectedModel: snapshot?.selectedModel,
    selectedKnowledgeBases: snapshot?.selectedKnowledgeBases ?? [],
    prompt: snapshot?.prompt ?? "",
    markdownTheme: snapshot?.markdownTheme ?? "light",
    pendingAttachments: snapshot?.pendingAttachments ?? [],
    messages: trimChatHistoryMessages(snapshot?.messages ?? []),
  };
}

export function loadChatHistorySnapshot(
  storage?: Storage,
): ChatHistorySnapshot | null {
  const targetStorage = getStorage(storage);
  if (!targetStorage) {
    return null;
  }

  try {
    const rawValue = targetStorage.getItem(CHAT_HISTORY_STORAGE_KEY);
    if (!rawValue) {
      return null;
    }

    const parsed = JSON.parse(rawValue) as PersistedChatHistorySnapshot;
    return normalizeChatHistorySnapshot({
      activeSessionId: parsed.activeSessionId,
      selectedModel: parsed.selectedModel,
      selectedKnowledgeBases: parsed.selectedKnowledgeBases ?? [],
      prompt: parsed.prompt ?? "",
      markdownTheme: parsed.markdownTheme ?? "light",
      pendingAttachments: parsed.pendingAttachments ?? [],
      messages: Array.isArray(parsed.messages)
        ? parsed.messages.map((message) => createChatHistoryMessage(message))
        : [],
    });
  } catch {
    return null;
  }
}

export function saveChatHistorySnapshot(
  snapshot: ChatHistorySnapshot,
  storage?: Storage,
): void {
  const targetStorage = getStorage(storage);
  if (!targetStorage) {
    return;
  }

  const normalized = normalizeChatHistorySnapshot(snapshot);
  const payload: PersistedChatHistorySnapshot = {
    version: 1,
    updatedAt: new Date().toISOString(),
    activeSessionId: normalized.activeSessionId,
    selectedModel: normalized.selectedModel,
    selectedKnowledgeBases: normalized.selectedKnowledgeBases,
    prompt: normalized.prompt,
    markdownTheme: normalized.markdownTheme,
    pendingAttachments: normalized.pendingAttachments,
    messages: normalized.messages,
  };

  targetStorage.setItem(CHAT_HISTORY_STORAGE_KEY, JSON.stringify(payload));
}

export function clearChatHistorySnapshot(storage?: Storage): void {
  const targetStorage = getStorage(storage);
  if (!targetStorage) {
    return;
  }

  targetStorage.removeItem(CHAT_HISTORY_STORAGE_KEY);
}
