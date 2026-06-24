import { Suspense, lazy, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Tag,
  Typography,
  message as antdMessage,
} from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { messages, type Locale } from "../i18n/messages";
import {
  api,
  API_BASE,
  type ChatAttachmentInfo,
  type ChatResponse,
  type ModelFeasibility,
  type ModelRecommendation,
  type SessionInfo,
  type TimeoutInfo,
} from "../services/api";
import type { MarkdownThemeName } from "../components/markdown/markdownThemes";
import {
  createChatHistoryMessage,
  loadChatHistorySnapshot,
  normalizeChatHistorySnapshot,
  saveChatHistorySnapshot,
  trimChatHistoryMessages,
  type ChatHistoryAttachment,
  type ChatHistoryMessage,
} from "../utils/chatHistoryStorage";
import { saveActiveModelPreference } from "../utils/activeModelPreference";
import { CreateKnowledgeBaseModal } from "../components/knowledgeBase/CreateKnowledgeBaseModal";
import {
  getUploadAcceptAttribute,
  prepareFileForUpload,
} from "../utils/uploadPolicy";

const { TextArea } = Input;
const { Paragraph, Text } = Typography;
const MarkdownRenderer = lazy(async () => ({
  default: (await import("../components/markdown/MarkdownRenderer"))
    .MarkdownRenderer,
}));

type UiMessage = ChatHistoryMessage;
type UiAttachment = ChatAttachmentInfo;
type CitationRecord = Record<string, unknown>;

function buildCitationLocator(
  citation: CitationRecord,
  copy: ReturnType<typeof getCopy>,
) {
  if (citation.page_no) {
    return `${copy.chat.citationPage} ${String(citation.page_no)}`;
  }
  if (citation.sheet_name) {
    return `${copy.chat.citationSheet} ${String(citation.sheet_name)}`;
  }
  if (citation.slide_no) {
    return `${copy.chat.citationSlide} ${String(citation.slide_no)}`;
  }
  return `${copy.chat.citationChunk} ${String(citation.chunk_index ?? 0)}`;
}

function buildCitationSourceLabel(
  citation: CitationRecord,
  copy: ReturnType<typeof getCopy>,
) {
  const sourceLabel = String(citation.source_label ?? "").trim();
  if (sourceLabel) {
    return sourceLabel;
  }
  return `${String(citation.file_name ?? "unknown")} · ${buildCitationLocator(citation, copy)}`;
}

function getCopy(locale: Locale) {
  return messages[locale];
}

function formatAttachmentSize(size: number): string {
  if (size >= 1024 * 1024) {
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
  }
  if (size >= 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${size} B`;
}

function buildAttachmentDownloadUrl(attachmentId: string): string {
  return `${API_BASE}/chat/attachments/${encodeURIComponent(attachmentId)}/download`;
}

function toHistoryAttachment(
  attachment: UiAttachment | ChatHistoryAttachment,
): ChatHistoryAttachment {
  return {
    id: attachment.id,
    session_id: attachment.session_id,
    message_id: attachment.message_id,
    file_name: attachment.file_name,
    file_ext: attachment.file_ext,
    mime_type: attachment.mime_type,
    file_size: attachment.file_size,
    attachment_type: attachment.attachment_type,
    storage_path: attachment.storage_path,
    extracted_text_preview: attachment.extracted_text_preview,
    ocr_status: attachment.ocr_status,
    status: attachment.status,
    created_at: attachment.created_at,
  };
}

function toUiAttachment(attachment: ChatHistoryAttachment): UiAttachment {
  return {
    id: attachment.id,
    session_id: attachment.session_id,
    message_id: attachment.message_id,
    file_name: attachment.file_name,
    file_ext: attachment.file_ext,
    mime_type: attachment.mime_type,
    file_size: attachment.file_size,
    attachment_type: attachment.attachment_type,
    storage_path: attachment.storage_path,
    extracted_text_preview: attachment.extracted_text_preview ?? "",
    ocr_status: attachment.ocr_status ?? "skipped",
    status: attachment.status ?? "uploaded",
    created_at: attachment.created_at,
  };
}

type ChatPageProps = {
  locale: Locale;
};

export function ChatPage({ locale }: ChatPageProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [initialHistorySnapshot] = useState(() =>
    normalizeChatHistorySnapshot(loadChatHistorySnapshot()),
  );
  const [selectedModel, setSelectedModel] = useState<string | undefined>(
    initialHistorySnapshot.selectedModel,
  );
  const [selectedKnowledgeBases, setSelectedKnowledgeBases] = useState<
    string[]
  >(initialHistorySnapshot.selectedKnowledgeBases);
  const [activeSessionId, setActiveSessionId] = useState<string | undefined>(
    initialHistorySnapshot.activeSessionId,
  );
  const [prompt, setPrompt] = useState(initialHistorySnapshot.prompt);
  const [chatMessages, setChatMessages] = useState<UiMessage[]>(
    initialHistorySnapshot.messages,
  );
  const [pendingAttachments, setPendingAttachments] = useState<UiAttachment[]>(
    initialHistorySnapshot.pendingAttachments.map(toUiAttachment),
  );
  const [isCreateKbOpen, setIsCreateKbOpen] = useState(false);
  const [isUploadingAttachment, setIsUploadingAttachment] = useState(false);
  const queryClient = useQueryClient();
  const copy = getCopy(locale);

  // Resource monitoring & model recommendation state
  const [resourceWarningOpen, setResourceWarningOpen] = useState(false);
  const [feasibility, setFeasibility] = useState<ModelFeasibility | null>(null);
  const [recommendations, setRecommendations] = useState<ModelRecommendation[]>(
    [],
  );
  const [timeoutInfo, setTimeoutInfo] = useState<TimeoutInfo | null>(null);
  const [timeoutOverride, setTimeoutOverride] = useState<number | null>(null);
  const [showTimeoutSettings, setShowTimeoutSettings] = useState(false);
  const [markdownTheme, setMarkdownTheme] = useState<MarkdownThemeName>(
    initialHistorySnapshot.markdownTheme,
  );

  const knowledgeBases = useQuery({
    queryKey: ["knowledge-bases"],
    queryFn: api.listKnowledgeBases,
  });
  const models = useQuery({
    queryKey: ["models"],
    queryFn: api.getModels,
  });

  // Initialize default model when query data arrives
  useEffect(() => {
    if (!selectedModel && models.data?.[0]?.name) {
      // Use queueMicrotask to defer state update outside the synchronous effect body
      queueMicrotask(() => setSelectedModel(models.data![0].name));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [models.data]);

  useEffect(() => {
    saveActiveModelPreference(selectedModel);
  }, [selectedModel]);

  const selectedModelInfo = useMemo(
    () => (models.data ?? []).find((item) => item.name === selectedModel),
    [models.data, selectedModel],
  );

  // -- Resource monitoring & model recommendation effects --
  // Check resource feasibility whenever the selected model changes
  useEffect(() => {
    if (!selectedModel) return;
    api
      .checkModelResources(selectedModel)
      .then((result) => {
        if (result.feasibility) {
          setFeasibility(result.feasibility);
          setRecommendations(result.recommendations || []);
          if (!result.feasibility.feasible) {
            setResourceWarningOpen(true);
          }
        }
      })
      .catch(() => {
        // Non-critical: silently ignore resource check failures
      });
  }, [selectedModel]);

  // Fetch timeout info whenever the selected model changes
  useEffect(() => {
    if (!selectedModel) return;
    api
      .getTimeoutInfo(selectedModel)
      .then(setTimeoutInfo)
      .catch(() => {});
  }, [selectedModel]);

  // Apply timeout override when changed
  useEffect(() => {
    api.setTimeoutOverride(timeoutOverride).catch(() => {});
  }, [timeoutOverride]);

  // Fetch recommendations on mount
  useEffect(() => {
    api
      .getModelRecommendations()
      .then(setRecommendations)
      .catch(() => {});
  }, []);

  const historySnapshot = useMemo(
    () =>
      normalizeChatHistorySnapshot({
        activeSessionId,
        selectedModel,
        selectedKnowledgeBases,
        prompt,
        markdownTheme,
        pendingAttachments: pendingAttachments.map(toHistoryAttachment),
        messages: chatMessages,
      }),
    [
      activeSessionId,
      chatMessages,
      markdownTheme,
      pendingAttachments,
      prompt,
      selectedKnowledgeBases,
      selectedModel,
    ],
  );

  useEffect(() => {
    saveChatHistorySnapshot(historySnapshot);
  }, [historySnapshot]);

  useEffect(() => {
    const handlePersist = () => {
      saveChatHistorySnapshot(historySnapshot);
    };

    window.addEventListener("beforeunload", handlePersist);
    window.addEventListener("pagehide", handlePersist);
    return () => {
      handlePersist();
      window.removeEventListener("beforeunload", handlePersist);
      window.removeEventListener("pagehide", handlePersist);
    };
  }, [historySnapshot]);

  const appendChatMessage = (
    message: Omit<UiMessage, "id" | "sentAt"> & {
      id?: string;
      sentAt?: string;
    },
  ) => {
    setChatMessages((current) =>
      trimChatHistoryMessages([...current, createChatHistoryMessage(message)]),
    );
  };

  const createSessionMutation = useMutation({
    mutationFn: (title: string) =>
      api.createSession({
        title,
        language: locale,
      }),
    onSuccess: (session: SessionInfo) => {
      setActiveSessionId(session.id);
      void queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });

  const chatMutation = useMutation({
    mutationFn: (payload: {
      sessionId: string;
      query: string;
      modelName: string;
      knowledgeBaseIds: string[];
      attachmentIds: string[];
      optimisticMessageId: string;
      attachmentSnapshots: UiAttachment[];
    }) =>
      api.chat({
        session_id: payload.sessionId,
        query: payload.query,
        model_name: payload.modelName,
        language: locale,
        knowledge_base_ids: payload.knowledgeBaseIds,
        attachment_ids: payload.attachmentIds,
      }),
    onSuccess: (response: ChatResponse, variables) => {
      setChatMessages((current) =>
        trimChatHistoryMessages([
          ...current.map((item) =>
            item.id === variables.optimisticMessageId
              ? {
                  ...item,
                  attachments: variables.attachmentSnapshots.map((attachment) =>
                    toHistoryAttachment({
                      ...attachment,
                      status: "linked",
                    }),
                  ),
                }
              : item,
          ),
          createChatHistoryMessage({
            role: "assistant",
            content: response.answer,
            modelName: response.model_used,
            citations: response.citations,
          }),
        ]),
      );
      setPendingAttachments((current) =>
        current.filter((item) => !variables.attachmentIds.includes(item.id)),
      );
      void queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
    onError: (error: Error) => {
      appendChatMessage({
        role: "assistant",
        content: error.message,
      });
      antdMessage.error(error.message);
    },
  });

  const handleAttachmentValidationFailure = (
    text: string,
    code?: "MODEL_UNSUPPORTED" | "INVALID_EXTENSION" | "FILE_TOO_LARGE",
  ) => {
    if (code === "MODEL_UNSUPPORTED") {
      Modal.warning({
        title: "当前模型不支持文件上传",
        content: text,
        okText: "我知道了",
      });
      return;
    }
    antdMessage.error(text);
  };

  const ensureActiveSession = async (): Promise<string> => {
    if (activeSessionId) {
      return activeSessionId;
    }
    const session = await createSessionMutation.mutateAsync(
      `Chat ${new Date().toLocaleTimeString()}`,
    );
    setActiveSessionId(session.id);
    return session.id;
  };

  const handleAttachmentSelection = async (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const selectedFiles = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (selectedFiles.length === 0) {
      return;
    }
    if (!selectedModel) {
      antdMessage.warning(copy.chat.modelLabel);
      return;
    }

    const sessionId = await ensureActiveSession();
    setIsUploadingAttachment(true);
    try {
      const uploadedAttachments: UiAttachment[] = [];
      for (const rawFile of selectedFiles) {
        const prepared = await prepareFileForUpload({
          file: rawFile,
          model: selectedModelInfo,
        });
        if (!prepared.ok) {
          handleAttachmentValidationFailure(prepared.message, prepared.code);
          continue;
        }
        try {
          const uploaded = await api.uploadChatAttachment({
            sessionId,
            file: prepared.file,
            enableOcr: true,
            modelName: selectedModel,
          });
          uploadedAttachments.push(uploaded);
        } catch (error) {
          antdMessage.error(
            error instanceof Error
              ? error.message
              : copy.chat.attachmentUploadFailed,
          );
        }
      }
      if (uploadedAttachments.length > 0) {
        setPendingAttachments((current) => [
          ...current,
          ...uploadedAttachments,
        ]);
        antdMessage.success(copy.chat.attachmentUploaded);
      }
    } finally {
      setIsUploadingAttachment(false);
    }
  };

  const handleRemovePendingAttachment = async (attachmentId: string) => {
    try {
      await api.deleteChatAttachment(attachmentId);
      setPendingAttachments((current) =>
        current.filter((item) => item.id !== attachmentId),
      );
    } catch (error) {
      antdMessage.error(
        error instanceof Error ? error.message : copy.chat.removeAttachment,
      );
    }
  };

  const cleanupPendingAttachments = async () => {
    const currentAttachments = [...pendingAttachments];
    if (currentAttachments.length === 0) {
      return;
    }
    await Promise.allSettled(
      currentAttachments.map((attachment) =>
        api.deleteChatAttachment(attachment.id),
      ),
    );
    setPendingAttachments([]);
  };

  const handleNewSession = async () => {
    await cleanupPendingAttachments();
    const session = await createSessionMutation.mutateAsync(
      `Chat ${new Date().toLocaleTimeString()}`,
    );
    setChatMessages([]);
    setPendingAttachments([]);
    setActiveSessionId(session.id);
  };

  const handleSend = async () => {
    if (!prompt.trim()) {
      return;
    }
    if (!selectedModel) {
      antdMessage.warning(copy.chat.modelLabel);
      return;
    }
    if (
      pendingAttachments.length > 0 &&
      selectedModelInfo?.supports_file_upload === false
    ) {
      handleAttachmentValidationFailure(
        "当前模型不支持文件上传，请切换到支持文件上传的多模态模型后重试。",
        "MODEL_UNSUPPORTED",
      );
      return;
    }

    const sessionId = await ensureActiveSession();

    const currentPrompt = prompt.trim();
    const currentPendingAttachments = [...pendingAttachments];
    setPrompt("");
    const optimisticMessage = createChatHistoryMessage({
      role: "user",
      content: currentPrompt,
      modelName: selectedModel,
    });
    setChatMessages((current) =>
      trimChatHistoryMessages([...current, optimisticMessage]),
    );

    try {
      await chatMutation.mutateAsync({
        sessionId,
        query: currentPrompt,
        modelName: selectedModel,
        knowledgeBaseIds: selectedKnowledgeBases,
        attachmentIds: currentPendingAttachments.map((item) => item.id),
        optimisticMessageId: optimisticMessage.id,
        attachmentSnapshots: currentPendingAttachments,
      });
    } catch {
      // The mutation error path already surfaces a readable UI message.
    }
  };

  return (
    <>
      <Card>
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <Row gutter={[12, 12]}>
            <Col xs={24} md={7}>
              <Text strong>{copy.chat.modelLabel}</Text>
              <Select
                style={{ width: "100%", marginTop: 8 }}
                placeholder={copy.chat.modelLabel}
                value={selectedModel}
                options={(models.data ?? []).map((item) => ({
                  label: item.name,
                  value: item.name,
                }))}
                onChange={setSelectedModel}
                loading={models.isLoading}
              />
            </Col>
            <Col xs={24} md={7}>
              <Text strong>{copy.chat.kbLabel}</Text>
              <Select
                mode="multiple"
                allowClear
                style={{ width: "100%", marginTop: 8 }}
                value={selectedKnowledgeBases}
                options={(knowledgeBases.data ?? []).map((item) => ({
                  label: String(item.name ?? item.id),
                  value: String(item.id),
                }))}
                onChange={setSelectedKnowledgeBases}
                placeholder={copy.chat.kbLabel}
              />
            </Col>
            <Col xs={24} md={3}>
              <Text strong>{copy.chat.activeModel}</Text>
              <div style={{ marginTop: 8 }}>
                <Tag color="blue">{selectedModel ?? copy.status.empty}</Tag>
              </div>
            </Col>
            <Col xs={24} md={3}>
              <Text strong>{copy.chat.themeLabel}</Text>
              <Select
                style={{ width: "100%", marginTop: 8 }}
                value={markdownTheme}
                options={[
                  { label: copy.chat.themeLight, value: "light" },
                  { label: copy.chat.themeDark, value: "dark" },
                  { label: copy.chat.themeEyeCare, value: "eyeCare" },
                ]}
                onChange={(value) => setMarkdownTheme(value)}
              />
            </Col>
            <Col xs={24} md={4}>
              <Text strong>&nbsp;</Text>
              <div style={{ marginTop: 8 }}>
                <Button block onClick={() => setIsCreateKbOpen(true)}>
                  {copy.chat.createKnowledgeBase}
                </Button>
              </div>
            </Col>
          </Row>

          <Card className="chat-panel" size="small">
            <Space direction="vertical" style={{ width: "100%" }} size="middle">
              {chatMessages.length === 0 ? (
                <Empty description={copy.status.empty} />
              ) : (
                chatMessages.map((item) => (
                  <div
                    key={item.id}
                    className={`chat-message chat-message-${item.role}`}
                  >
                    <Text strong>
                      {item.role === "user" ? "User" : "Assistant"}
                    </Text>
                    {item.modelName ? (
                      <Tag style={{ marginLeft: 8 }}>{item.modelName}</Tag>
                    ) : null}
                    <div style={{ marginTop: 8 }}>
                      <Suspense
                        fallback={<Text type="secondary">Rendering...</Text>}
                      >
                        <MarkdownRenderer
                          content={item.content}
                          themeName={markdownTheme}
                          className="markdown-chat-content"
                          height={320}
                          streaming={chatMutation.isPending}
                        />
                      </Suspense>
                    </div>
                    {item.attachments && item.attachments.length > 0 ? (
                      <Space
                        direction="vertical"
                        size={6}
                        style={{ width: "100%", marginTop: 12 }}
                      >
                        <Text type="secondary">{copy.chat.attachedFiles}</Text>
                        {item.attachments.map((attachment) => (
                          <Card key={attachment.id} size="small">
                            <Space
                              align="center"
                              style={{
                                width: "100%",
                                justifyContent: "space-between",
                              }}
                              wrap
                            >
                              <Space direction="vertical" size={2}>
                                <Text strong>{attachment.file_name}</Text>
                                <Text type="secondary">
                                  {attachment.attachment_type} ·{" "}
                                  {formatAttachmentSize(attachment.file_size)}
                                </Text>
                                {attachment.extracted_text_preview ? (
                                  <Text type="secondary">
                                    {attachment.extracted_text_preview}
                                  </Text>
                                ) : null}
                              </Space>
                              <a
                                href={buildAttachmentDownloadUrl(attachment.id)}
                                target="_blank"
                                rel="noreferrer"
                              >
                                {copy.chat.downloadAttachment}
                              </a>
                            </Space>
                          </Card>
                        ))}
                      </Space>
                    ) : null}
                    {item.citations && item.citations.length > 0 ? (
                      <Space
                        direction="vertical"
                        size={4}
                        style={{ width: "100%" }}
                      >
                        <Text type="secondary">{copy.chat.citations}</Text>
                        {item.citations
                          .slice(0, 3)
                          .map((citation, citationIndex) => (
                            <Card key={citationIndex} size="small">
                              <Space
                                direction="vertical"
                                size={4}
                                style={{ width: "100%" }}
                              >
                                <Text strong>
                                  {String(citation.file_name ?? "unknown")}
                                </Text>
                                <Text type="secondary">
                                  {copy.chat.citationSource}:{" "}
                                  {buildCitationSourceLabel(
                                    citation as CitationRecord,
                                    copy,
                                  )}
                                </Text>
                                <Space size={[6, 6]} wrap>
                                  <Tag>
                                    {buildCitationLocator(
                                      citation as CitationRecord,
                                      copy,
                                    )}
                                  </Tag>
                                  <Tag color="blue">
                                    {copy.chat.citationScore}:{" "}
                                    {String(citation.score ?? 0)}
                                  </Tag>
                                  {Array.isArray(citation.matched_terms) &&
                                  citation.matched_terms.length > 0 ? (
                                    <Tag color="purple">
                                      {copy.chat.citationMatchedTerms}:{" "}
                                      {citation.matched_terms.join(", ")}
                                    </Tag>
                                  ) : null}
                                  {citation.heading_path ? (
                                    <Tag color="cyan">
                                      {copy.chat.citationSection}:{" "}
                                      {String(citation.heading_path)}
                                    </Tag>
                                  ) : null}
                                </Space>
                                <Text type="secondary">
                                  {copy.chat.citationQuote}
                                </Text>
                                <Text style={{ whiteSpace: "pre-wrap" }}>
                                  {String(
                                    citation.quote_excerpt ??
                                      citation.quote_text ??
                                      "",
                                  )}
                                </Text>
                              </Space>
                            </Card>
                          ))}
                      </Space>
                    ) : null}
                  </div>
                ))
              )}
              {chatMutation.isPending ? (
                <Text type="secondary">{copy.status.thinking}</Text>
              ) : null}
            </Space>
          </Card>

          <TextArea
            rows={4}
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder={copy.chat.inputPlaceholder}
          />

          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={getUploadAcceptAttribute()}
            style={{ display: "none" }}
            onChange={(event) => void handleAttachmentSelection(event)}
          />

          {pendingAttachments.length > 0 ? (
            <Card size="small" title={copy.chat.pendingAttachments}>
              <Space
                direction="vertical"
                style={{ width: "100%" }}
                size="small"
              >
                {pendingAttachments.map((attachment) => (
                  <Space
                    key={attachment.id}
                    align="center"
                    style={{ width: "100%", justifyContent: "space-between" }}
                    wrap
                  >
                    <Space direction="vertical" size={2}>
                      <Text strong>{attachment.file_name}</Text>
                      <Text type="secondary">
                        {attachment.attachment_type} ·{" "}
                        {formatAttachmentSize(attachment.file_size)}
                      </Text>
                    </Space>
                    <Button
                      size="small"
                      onClick={() =>
                        void handleRemovePendingAttachment(attachment.id)
                      }
                    >
                      {copy.chat.removeAttachment}
                    </Button>
                  </Space>
                ))}
              </Space>
            </Card>
          ) : null}

          <Text type="secondary">{copy.chat.chatUploadHint}</Text>

          <Space>
            <Button onClick={() => void handleNewSession()}>
              {copy.chat.newSession}
            </Button>
            <Button
              onClick={() => fileInputRef.current?.click()}
              loading={isUploadingAttachment}
            >
              {copy.chat.chatUploadFiles}
            </Button>
            <Button onClick={() => setShowTimeoutSettings(true)}>
              {copy.chat.timeoutSettings}
            </Button>
            <Button
              type="primary"
              onClick={() => void handleSend()}
              loading={
                chatMutation.isPending || createSessionMutation.isPending
              }
            >
              {copy.chat.send}
            </Button>
          </Space>
        </Space>
      </Card>

      <CreateKnowledgeBaseModal
        locale={locale}
        open={isCreateKbOpen}
        activeModel={selectedModelInfo}
        onClose={() => setIsCreateKbOpen(false)}
        onCreated={(kbId) => {
          setSelectedKnowledgeBases((current) =>
            Array.from(new Set([...current, kbId])),
          );
        }}
      />

      {/* -- Resource warning modal -- */}
      <Modal
        title="Resource Warning"
        open={resourceWarningOpen}
        onCancel={() => setResourceWarningOpen(false)}
        onOk={() => setResourceWarningOpen(false)}
        okText="I understand"
        width={640}
      >
        {feasibility && (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <Alert
              type="warning"
              message="Insufficient Hardware Resources"
              description={`Your device may not have enough resources to run ${selectedModel}. Please review the details below.`}
              showIcon
            />

            <Descriptions title="Your Device" bordered size="small" column={2}>
              <Descriptions.Item label="Available RAM">
                {feasibility.current_resources.memory.available_gb ?? "N/A"} GB
              </Descriptions.Item>
              <Descriptions.Item label="Total RAM">
                {feasibility.current_resources.memory.total_gb ?? "N/A"} GB
              </Descriptions.Item>
              <Descriptions.Item label="CPU Cores">
                {feasibility.current_resources.cpu.cpu_cores_logical ?? "N/A"}
              </Descriptions.Item>
              <Descriptions.Item label="GPU Available">
                {feasibility.current_resources.gpu.available ? "Yes" : "No"}
              </Descriptions.Item>
            </Descriptions>

            {feasibility.model_requirement && (
              <Descriptions
                title={`${selectedModel} Requires`}
                bordered
                size="small"
                column={2}
              >
                <Descriptions.Item label="RAM">
                  {feasibility.model_requirement.ram_gb} GB
                </Descriptions.Item>
                <Descriptions.Item label="VRAM">
                  {feasibility.model_requirement.vram_gb ?? "CPU-only"} GB
                </Descriptions.Item>
                <Descriptions.Item label="CPU Cores">
                  {feasibility.model_requirement.cpu_cores}
                </Descriptions.Item>
                <Descriptions.Item label="Description">
                  {feasibility.model_requirement.description}
                </Descriptions.Item>
              </Descriptions>
            )}

            {feasibility.warnings.length > 0 && (
              <div>
                <Text strong>Warnings:</Text>
                {feasibility.warnings.map((w, i) => (
                  <Alert
                    key={i}
                    type="warning"
                    message={w}
                    style={{ marginTop: 4 }}
                  />
                ))}
              </div>
            )}

            {feasibility.recommendation && (
              <Alert
                type="info"
                message={`Recommendation: Switch to ${feasibility.recommendation.suggested_display_name} (${feasibility.recommendation.suggested_model})`}
                description={
                  <div>
                    <Paragraph style={{ marginBottom: 8 }}>
                      {feasibility.recommendation.reason}
                    </Paragraph>
                    <Button
                      type="primary"
                      size="small"
                      onClick={() => {
                        setSelectedModel(
                          models.data?.find(
                            (m) =>
                              m.name
                                .toLowerCase()
                                .includes(
                                  feasibility.recommendation!.suggested_model.toLowerCase(),
                                ) ||
                              m.name
                                .toLowerCase()
                                .includes(
                                  feasibility
                                    .recommendation!.suggested_model.replace(
                                      "B",
                                      "b",
                                    )
                                    .toLowerCase(),
                                ),
                          )?.name ?? selectedModel,
                        );
                        setResourceWarningOpen(false);
                        antdMessage.success(
                          `Switched to ${feasibility.recommendation!.suggested_display_name}`,
                        );
                      }}
                    >
                      Switch to{" "}
                      {feasibility.recommendation.suggested_display_name}
                    </Button>
                  </div>
                }
                showIcon
              />
            )}
          </Space>
        )}
      </Modal>

      {/* -- Timeout settings modal -- */}
      <Modal
        title={copy.chat.timeoutSettings}
        open={showTimeoutSettings}
        onCancel={() => setShowTimeoutSettings(false)}
        onOk={() => setShowTimeoutSettings(false)}
        okText={copy.chat.timeoutDone}
        width={480}
      >
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          {timeoutInfo ? (
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label={copy.chat.timeoutCurrentModel}>
                {timeoutInfo.model_name}
              </Descriptions.Item>
              <Descriptions.Item label={copy.chat.timeoutParamSize}>
                {timeoutInfo.param_size}
              </Descriptions.Item>
              <Descriptions.Item label={copy.chat.timeoutConnect}>
                {timeoutInfo.timeout.connect}s
              </Descriptions.Item>
              <Descriptions.Item label={copy.chat.timeoutRead}>
                {timeoutInfo.timeout.read}s
              </Descriptions.Item>
              <Descriptions.Item label={copy.chat.timeoutWrite}>
                {timeoutInfo.timeout.write}s
              </Descriptions.Item>
              <Descriptions.Item label={copy.chat.timeoutAutoTiered}>
                {timeoutInfo.user_override
                  ? copy.chat.timeoutAutoNoManual
                  : copy.chat.timeoutAutoYes}
              </Descriptions.Item>
            </Descriptions>
          ) : (
            <Text type="secondary">{copy.chat.timeoutSelectModelFirst}</Text>
          )}

          <div>
            <Text strong>{copy.chat.timeoutManualReadOverride}</Text>
            <InputNumber
              style={{ width: "100%", marginTop: 8 }}
              min={10}
              max={3600}
              placeholder={copy.chat.timeoutPlaceholder}
              value={timeoutOverride}
              onChange={(value) => setTimeoutOverride(value)}
            />
            <Paragraph type="secondary" style={{ marginTop: 4 }}>
              {copy.chat.timeoutHelp}
            </Paragraph>
            {timeoutOverride && (
              <Button
                size="small"
                danger
                style={{ marginTop: 4 }}
                onClick={() => setTimeoutOverride(null)}
              >
                {copy.chat.timeoutRevertAuto}
              </Button>
            )}
          </div>
        </Space>
      </Modal>

      {/* -- Model recommendations sidebar -- */}
      {recommendations.length > 0 && (
        <Card
          size="small"
          title="Model Suitability for This Device"
          style={{ marginTop: 12 }}
        >
          <Row gutter={[8, 8]}>
            {recommendations.map((rec) => (
              <Col key={rec.param_size} xs={24} sm={12} md={8} lg={4}>
                <Card
                  size="small"
                  hoverable
                  style={{
                    borderColor: rec.feasible ? "#52c41a" : "#ff4d4f",
                  }}
                  onClick={() => {
                    const match = (models.data ?? []).find(
                      (m) =>
                        m.name
                          .toLowerCase()
                          .includes(rec.param_size.toLowerCase()) ||
                        m.name
                          .toLowerCase()
                          .includes(
                            rec.param_size.replace("B", "b").toLowerCase(),
                          ),
                    );
                    if (match) {
                      setSelectedModel(match.name);
                      antdMessage.info(`Selected ${match.name}`);
                    }
                  }}
                >
                  <Space direction="vertical" size={2}>
                    <Text strong>{rec.display_name || rec.param_size}</Text>
                    <Tag color={rec.feasible ? "green" : "red"}>
                      {rec.feasible ? "Runnable" : "Insufficient"}
                    </Tag>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      RAM: {rec.ram_gb}GB
                      {rec.vram_gb ? ` | VRAM: ${rec.vram_gb}GB` : " | CPU"}
                    </Text>
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>
      )}
    </>
  );
}
