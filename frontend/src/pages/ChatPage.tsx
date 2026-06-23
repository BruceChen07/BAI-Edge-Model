import { Suspense, lazy, useEffect, useMemo, useState } from "react";
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
  type ChatHistoryMessage,
} from "../utils/chatHistoryStorage";
import { CreateKnowledgeBaseModal } from "../components/knowledgeBase/CreateKnowledgeBaseModal";

const { TextArea } = Input;
const { Paragraph, Text } = Typography;
const MarkdownRenderer = lazy(async () => ({
  default: (await import("../components/markdown/MarkdownRenderer"))
    .MarkdownRenderer,
}));

type UiMessage = ChatHistoryMessage;
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

type ChatPageProps = {
  locale: Locale;
};

export function ChatPage({ locale }: ChatPageProps) {
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
  const [isCreateKbOpen, setIsCreateKbOpen] = useState(false);
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
        messages: chatMessages,
      }),
    [
      activeSessionId,
      chatMessages,
      markdownTheme,
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
    }) =>
      api.chat({
        session_id: payload.sessionId,
        query: payload.query,
        model_name: payload.modelName,
        language: locale,
        knowledge_base_ids: payload.knowledgeBaseIds,
      }),
    onSuccess: (response: ChatResponse) => {
      appendChatMessage({
        role: "assistant",
        content: response.answer,
        modelName: response.model_used,
        citations: response.citations,
      });
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

  const handleNewSession = async () => {
    const session = await createSessionMutation.mutateAsync(
      `Chat ${new Date().toLocaleTimeString()}`,
    );
    setChatMessages([]);
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

    let sessionId = activeSessionId;
    if (!sessionId) {
      const session = await createSessionMutation.mutateAsync(
        `Chat ${new Date().toLocaleTimeString()}`,
      );
      sessionId = session.id;
      setActiveSessionId(session.id);
    }

    const currentPrompt = prompt.trim();
    setPrompt("");
    appendChatMessage({
      role: "user",
      content: currentPrompt,
      modelName: selectedModel,
    });

    await chatMutation.mutateAsync({
      sessionId,
      query: currentPrompt,
      modelName: selectedModel,
      knowledgeBaseIds: selectedKnowledgeBases,
    });
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

          <Space>
            <Button onClick={() => void handleNewSession()}>
              {copy.chat.newSession}
            </Button>
            <Button onClick={() => setShowTimeoutSettings(true)}>
              Timeout Settings
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
        title="Timeout Settings"
        open={showTimeoutSettings}
        onCancel={() => setShowTimeoutSettings(false)}
        onOk={() => setShowTimeoutSettings(false)}
        okText="Done"
        width={480}
      >
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          {timeoutInfo ? (
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label="Current Model">
                {timeoutInfo.model_name}
              </Descriptions.Item>
              <Descriptions.Item label="Param Size">
                {timeoutInfo.param_size}
              </Descriptions.Item>
              <Descriptions.Item label="Connect Timeout">
                {timeoutInfo.timeout.connect}s
              </Descriptions.Item>
              <Descriptions.Item label="Read Timeout">
                {timeoutInfo.timeout.read}s
              </Descriptions.Item>
              <Descriptions.Item label="Write Timeout">
                {timeoutInfo.timeout.write}s
              </Descriptions.Item>
              <Descriptions.Item label="Auto-tiered">
                {timeoutInfo.user_override ? "No (Manual)" : "Yes"}
              </Descriptions.Item>
            </Descriptions>
          ) : (
            <Text type="secondary">
              Select a model first to see timeout info.
            </Text>
          )}

          <div>
            <Text strong>Manual Read Timeout Override (seconds):</Text>
            <InputNumber
              style={{ width: "100%", marginTop: 8 }}
              min={10}
              max={3600}
              placeholder="10 - 3600 seconds"
              value={timeoutOverride}
              onChange={(value) => setTimeoutOverride(value)}
            />
            <Paragraph type="secondary" style={{ marginTop: 4 }}>
              Set a custom read timeout. Leave empty to use auto-tiered
              selection based on model size.
            </Paragraph>
            {timeoutOverride && (
              <Button
                size="small"
                danger
                style={{ marginTop: 4 }}
                onClick={() => setTimeoutOverride(null)}
              >
                Revert to Auto
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
