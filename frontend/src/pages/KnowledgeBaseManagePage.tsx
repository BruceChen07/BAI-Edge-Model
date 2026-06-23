import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  Progress,
  Select,
  message as antdMessage,
  Popconfirm,
  Row,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  Upload,
} from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { messages, type Locale } from "../i18n/messages";
import {
  API_BASE,
  api,
  type ExportResult,
  type KnowledgeBaseChunk,
  type KnowledgeBaseInfo,
  type KnowledgeBaseStats,
} from "../services/api";
import { CreateKnowledgeBaseModal } from "../components/knowledgeBase/CreateKnowledgeBaseModal";

const { Text, Title } = Typography;

type KnowledgeBaseManagePageProps = {
  locale: Locale;
};

type KnowledgeBaseFile = {
  id: string;
  kb_id: string;
  file_name: string;
  file_size: number;
  parse_status: string;
  ocr_status: string;
  index_status: string;
};

function formatBytes(value?: number | null) {
  const size = value ?? 0;
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  if (size < 1024 * 1024 * 1024) {
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
  }
  return `${(size / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

function formatDate(value?: string | null) {
  if (!value) {
    return "-";
  }
  return value.replace("T", " ").slice(0, 19);
}

function getChunkLocator(
  chunk: KnowledgeBaseChunk,
  copy: ReturnType<typeof getCopy>,
) {
  if (chunk.page_no) {
    return `${copy.chat.citationPage} ${chunk.page_no}`;
  }
  if (chunk.sheet_name) {
    return `${copy.chat.citationSheet} ${chunk.sheet_name}`;
  }
  if (chunk.slide_no) {
    return `${copy.chat.citationSlide} ${chunk.slide_no}`;
  }
  return `${copy.chat.citationChunk} ${chunk.chunk_index}`;
}

function getCopy(locale: Locale) {
  return messages[locale];
}

export function KnowledgeBaseManagePage({
  locale,
}: KnowledgeBaseManagePageProps) {
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [selectedKbId, setSelectedKbId] = useState<string | null>(null);
  const [searchKeyword, setSearchKeyword] = useState("");
  const [chunkOffset, setChunkOffset] = useState(0);
  const [chunkLimit, setChunkLimit] = useState(10);
  const [chunkDocumentId, setChunkDocumentId] = useState<string | undefined>();
  const [activeReindexTaskId, setActiveReindexTaskId] = useState<string | null>(
    null,
  );
  const [renameForm] = Form.useForm();
  const queryClient = useQueryClient();
  const copy = getCopy(locale);

  const knowledgeBases = useQuery({
    queryKey: ["knowledge-bases"],
    queryFn: api.listKnowledgeBases,
  });

  const filteredKnowledgeBases = useMemo(() => {
    const keyword = searchKeyword.trim().toLowerCase();
    const source = knowledgeBases.data ?? [];
    if (!keyword) {
      return source;
    }
    return source.filter(
      (kb) =>
        kb.name.toLowerCase().includes(keyword) ||
        kb.description.toLowerCase().includes(keyword),
    );
  }, [knowledgeBases.data, searchKeyword]);

  const effectiveSelectedKbId =
    selectedKbId ?? filteredKnowledgeBases[0]?.id ?? null;
  const selectedKb =
    filteredKnowledgeBases.find((kb) => kb.id === effectiveSelectedKbId) ??
    knowledgeBases.data?.find((kb) => kb.id === effectiveSelectedKbId);

  useEffect(() => {
    if (selectedKb) {
      renameForm.setFieldsValue({
        name: selectedKb.name,
        description: selectedKb.description,
      });
    }
  }, [renameForm, selectedKb]);

  const files = useQuery({
    queryKey: ["knowledge-base-files", effectiveSelectedKbId],
    queryFn: () =>
      effectiveSelectedKbId
        ? api.listKnowledgeBaseFiles(effectiveSelectedKbId)
        : Promise.resolve([]),
    enabled: !!effectiveSelectedKbId,
  });

  const stats = useQuery({
    queryKey: ["knowledge-base-stats", effectiveSelectedKbId],
    queryFn: () =>
      effectiveSelectedKbId
        ? api.getKnowledgeBaseStats(effectiveSelectedKbId)
        : Promise.resolve(null as unknown as KnowledgeBaseStats),
    enabled: !!effectiveSelectedKbId,
  });

  const chunks = useQuery({
    queryKey: [
      "knowledge-base-chunks",
      effectiveSelectedKbId,
      chunkDocumentId,
      chunkOffset,
      chunkLimit,
    ],
    queryFn: () =>
      effectiveSelectedKbId
        ? api.listKnowledgeBaseChunks({
            kbId: effectiveSelectedKbId,
            documentId: chunkDocumentId,
            offset: chunkOffset,
            limit: chunkLimit,
          })
        : Promise.resolve({
            items: [],
            total: 0,
            offset: 0,
            limit: chunkLimit,
          }),
    enabled: !!effectiveSelectedKbId,
  });

  const activeTask = useQuery({
    queryKey: ["task", activeReindexTaskId],
    queryFn: () =>
      activeReindexTaskId
        ? api.getTask(activeReindexTaskId)
        : Promise.resolve(null as unknown as Record<string, unknown>),
    enabled: !!activeReindexTaskId,
    refetchInterval: (query) => {
      const data = query.state.data as Record<string, unknown> | undefined;
      if (!data) {
        return 1200;
      }
      const status = String(data.status ?? "");
      if (status === "done" && effectiveSelectedKbId) {
        void queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
        void queryClient.invalidateQueries({
          queryKey: ["knowledge-base-chunks", effectiveSelectedKbId],
        });
        void queryClient.invalidateQueries({
          queryKey: ["knowledge-base-stats", effectiveSelectedKbId],
        });
        return false;
      }
      return status === "running" || status === "pending" ? 1200 : false;
    },
  });

  const deleteKbMutation = useMutation({
    mutationFn: (kbId: string) => api.deleteKnowledgeBase(kbId),
    onSuccess: () => {
      antdMessage.success(copy.kbManagement.deleted);
      setSelectedKbId(null);
      void queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
    },
    onError: (error: Error) => {
      antdMessage.error(error.message);
    },
  });

  const renameKbMutation = useMutation({
    mutationFn: (payload: { id: string; name: string; description?: string }) =>
      api.updateKnowledgeBase(payload),
    onSuccess: () => {
      antdMessage.success(copy.kbManagement.renamed);
      void queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
    },
    onError: (error: Error) => {
      antdMessage.error(error.message);
    },
  });

  const deleteFileMutation = useMutation({
    mutationFn: (payload: { kbId: string; fileId: string }) =>
      api.deleteKnowledgeBaseFile(payload.kbId, payload.fileId),
    onSuccess: () => {
      antdMessage.success(copy.kbManagement.deleted);
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-base-files", selectedKbId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-base-chunks", selectedKbId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-base-stats", selectedKbId],
      });
      void queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
    },
    onError: (error: Error) => {
      antdMessage.error(error.message);
    },
  });

  const uploadFileMutation = useMutation({
    mutationFn: async (payload: { kbId: string; file: File }) => {
      return api.uploadKnowledgeBaseFile({
        kbId: payload.kbId,
        file: payload.file,
        enableOcr: true,
      });
    },
    onSuccess: () => {
      antdMessage.success(copy.kbManagement.uploaded);
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-base-files", selectedKbId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-base-chunks", selectedKbId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["knowledge-base-stats", selectedKbId],
      });
      void queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
    },
    onError: (error: Error) => {
      antdMessage.error(error.message);
    },
  });

  const reindexMutation = useMutation({
    mutationFn: (kbId: string) => api.reindexKnowledgeBase(kbId),
    onSuccess: (task) => {
      antdMessage.success(copy.kbManagement.reindexStarted);
      setActiveReindexTaskId(String(task.id ?? ""));
    },
    onError: (error: Error) => {
      antdMessage.error(error.message);
    },
  });

  const exportMutation = useMutation({
    mutationFn: async (payload: {
      format: "markdown" | "docx" | "xlsx";
      kb: KnowledgeBaseInfo;
    }) => {
      if (payload.format === "markdown") {
        return api.createMarkdownExport({
          source_type: "knowledge_base",
          source_id: payload.kb.id,
          title: payload.kb.name,
        });
      }
      if (payload.format === "docx") {
        return api.createDocxExport({
          source_type: "knowledge_base",
          source_id: payload.kb.id,
          title: payload.kb.name,
        });
      }
      return api.createXlsxExport({
        source_type: "knowledge_base",
        source_id: payload.kb.id,
        title: payload.kb.name,
      });
    },
    onSuccess: (result: ExportResult) => {
      window.open(`${API_BASE}/exports/${result.export_id}/download`, "_blank");
    },
    onError: (error: Error) => {
      antdMessage.error(error.message);
    },
  });

  const kbColumns = [
    {
      title: copy.catalog.model,
      dataIndex: "name",
      key: "name",
      sorter: (a: KnowledgeBaseInfo, b: KnowledgeBaseInfo) =>
        a.name.localeCompare(b.name),
      render: (name: string) => <Text strong>{name}</Text>,
    },
    {
      title: copy.catalog.description,
      dataIndex: "description",
      key: "description",
      ellipsis: true,
    },
    {
      title: copy.chat.uploadFiles,
      dataIndex: "file_count",
      key: "file_count",
      width: 90,
      sorter: (a: KnowledgeBaseInfo, b: KnowledgeBaseInfo) =>
        a.file_count - b.file_count,
    },
    {
      title: copy.panels.tasks,
      dataIndex: "chunk_count",
      key: "chunk_count",
      width: 90,
      sorter: (a: KnowledgeBaseInfo, b: KnowledgeBaseInfo) =>
        a.chunk_count - b.chunk_count,
    },
    {
      title: copy.kbManagement.createdAt,
      dataIndex: "created_at",
      key: "created_at",
      width: 160,
      sorter: (a: KnowledgeBaseInfo, b: KnowledgeBaseInfo) =>
        String(a.created_at ?? "").localeCompare(String(b.created_at ?? "")),
      render: (value: string | null | undefined) => formatDate(value),
    },
    {
      title: copy.downloads.status,
      dataIndex: "status",
      key: "status",
      width: 110,
      filters: [
        { text: copy.kbManagement.statusReady, value: "ready" },
        { text: copy.kbManagement.statusOther, value: "reindexing" },
        { text: "error", value: "error" },
      ],
      onFilter: (value: boolean | React.Key, record: KnowledgeBaseInfo) =>
        record.status === value,
      render: (status: string) => (
        <Tag
          color={
            status === "ready" ? "green" : status === "error" ? "red" : "orange"
          }
        >
          {status}
        </Tag>
      ),
    },
  ];

  const fileOptions = useMemo(() => {
    const fileList = (files.data ?? []) as KnowledgeBaseFile[];
    return [
      { label: copy.kbManagement.filterAllFiles, value: "" },
      ...fileList.map((file) => ({ label: file.file_name, value: file.id })),
    ];
  }, [copy.kbManagement.filterAllFiles, files.data]);

  const fileColumns = [
    {
      title: copy.kbManagement.fileName,
      dataIndex: "file_name",
      key: "file_name",
    },
    {
      title: copy.catalog.size,
      dataIndex: "file_size",
      key: "file_size",
      render: (size: number) => formatBytes(size),
    },
    {
      title: copy.kbManagement.parseStatus,
      dataIndex: "parse_status",
      key: "parse_status",
      render: (status: string) => (
        <Tag color={status === "done" ? "green" : "orange"}>{status}</Tag>
      ),
    },
    {
      title: copy.kbManagement.ocrStatus,
      dataIndex: "ocr_status",
      key: "ocr_status",
      render: (status: string) => (
        <Tag color={status === "done" ? "green" : "default"}>{status}</Tag>
      ),
    },
    {
      title: copy.downloads.action,
      key: "action",
      render: (_: unknown, record: KnowledgeBaseFile) => (
        <Popconfirm
          title={copy.kbManagement.deleteFileConfirm}
          onConfirm={() => {
            if (!selectedKbId) {
              return;
            }
            deleteFileMutation.mutate({
              kbId: selectedKbId,
              fileId: record.id,
            });
          }}
        >
          <Button size="small" danger>
            {copy.kbManagement.deleteFile}
          </Button>
        </Popconfirm>
      ),
    },
  ];

  const chunkColumns = [
    {
      title: copy.kbManagement.fileName,
      dataIndex: "file_name",
      key: "file_name",
      width: 180,
      ellipsis: true,
    },
    {
      title: copy.kbManagement.chunkIndex,
      dataIndex: "chunk_index",
      key: "chunk_index",
      width: 100,
    },
    {
      title: copy.chat.citationPage,
      key: "locator",
      width: 140,
      render: (_: unknown, record: KnowledgeBaseChunk) =>
        getChunkLocator(record, copy),
    },
    {
      title: copy.kbManagement.chunkPreview,
      dataIndex: "content",
      key: "content",
      render: (content: string) => (
        <Text style={{ whiteSpace: "pre-wrap" }}>
          {content.length > 220 ? `${content.slice(0, 220)}...` : content}
        </Text>
      ),
    },
  ];

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Row align="middle" justify="space-between" gutter={[12, 12]}>
        <Col flex="auto">
          <Title level={4}>{copy.kbManagement.pageTitle}</Title>
        </Col>
        <Col flex="320px">
          <Input
            value={searchKeyword}
            onChange={(event) => setSearchKeyword(event.target.value)}
            placeholder={copy.kbManagement.searchPlaceholder}
          />
        </Col>
        <Col>
          <Button type="primary" onClick={() => setIsCreateOpen(true)}>
            {copy.kbManagement.create}
          </Button>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} lg={selectedKb ? 10 : 24}>
          <Card>
            <Table
              dataSource={filteredKnowledgeBases}
              columns={kbColumns}
              rowKey="id"
              loading={knowledgeBases.isLoading}
              size="middle"
              pagination={{ pageSize: 8 }}
              onRow={(record) => ({
                onClick: () => {
                  setSelectedKbId(
                    record.id === selectedKbId ? null : record.id,
                  );
                  setChunkDocumentId(undefined);
                  setChunkOffset(0);
                },
                style: {
                  cursor: "pointer",
                  background:
                    record.id === selectedKbId ? "#e6f4ff" : undefined,
                },
              })}
            />
          </Card>
        </Col>

        {selectedKb ? (
          <Col xs={24} lg={14}>
            <Card
              title={selectedKb.name}
              extra={
                <Space wrap>
                  <Button
                    onClick={() =>
                      exportMutation.mutate({
                        format: "markdown",
                        kb: selectedKb,
                      })
                    }
                    loading={exportMutation.isPending}
                  >
                    {copy.kbManagement.exportMarkdown}
                  </Button>
                  <Button
                    onClick={() =>
                      exportMutation.mutate({ format: "docx", kb: selectedKb })
                    }
                    loading={exportMutation.isPending}
                  >
                    {copy.kbManagement.exportDocx}
                  </Button>
                  <Button
                    onClick={() =>
                      exportMutation.mutate({ format: "xlsx", kb: selectedKb })
                    }
                    loading={exportMutation.isPending}
                  >
                    {copy.kbManagement.exportXlsx}
                  </Button>
                  <Popconfirm
                    title={copy.kbManagement.deleteKbConfirm}
                    description={copy.kbManagement.deleteKbDesc}
                    onConfirm={() => deleteKbMutation.mutate(selectedKb.id)}
                  >
                    <Button danger loading={deleteKbMutation.isPending}>
                      {copy.kbManagement.deleteKb}
                    </Button>
                  </Popconfirm>
                </Space>
              }
            >
              {activeTask.data &&
              String(activeTask.data.related_id ?? "") === selectedKb.id ? (
                <Card size="small" style={{ marginBottom: 16 }}>
                  <Space direction="vertical" style={{ width: "100%" }}>
                    <Text>{copy.kbManagement.reindexing}</Text>
                    <Progress
                      percent={Math.round(
                        Number(activeTask.data.progress ?? 0) * 100,
                      )}
                    />
                  </Space>
                </Card>
              ) : null}

              <Tabs
                items={[
                  {
                    key: "info",
                    label: copy.kbManagement.infoTab,
                    children: (
                      <Space
                        direction="vertical"
                        style={{ width: "100%" }}
                        size="middle"
                      >
                        <Descriptions bordered size="small" column={2}>
                          <Descriptions.Item label="ID">
                            {selectedKb.id}
                          </Descriptions.Item>
                          <Descriptions.Item label={copy.downloads.status}>
                            <Tag
                              color={
                                selectedKb.status === "ready"
                                  ? "green"
                                  : "orange"
                              }
                            >
                              {selectedKb.status}
                            </Tag>
                          </Descriptions.Item>
                          <Descriptions.Item label={copy.chat.uploadFiles}>
                            {selectedKb.file_count}
                          </Descriptions.Item>
                          <Descriptions.Item label={copy.panels.tasks}>
                            {selectedKb.chunk_count}
                          </Descriptions.Item>
                          <Descriptions.Item
                            label={copy.kbManagement.createdAt}
                          >
                            {formatDate(selectedKb.created_at)}
                          </Descriptions.Item>
                          <Descriptions.Item
                            label={copy.kbManagement.updatedAt}
                          >
                            {formatDate(selectedKb.updated_at)}
                          </Descriptions.Item>
                          <Descriptions.Item
                            label={copy.kbManagement.storageSize}
                          >
                            {formatBytes(stats.data?.total_size_bytes)}
                          </Descriptions.Item>
                          <Descriptions.Item
                            label={copy.kbManagement.tokenCount}
                          >
                            {stats.data?.token_count ?? 0}
                          </Descriptions.Item>
                          <Descriptions.Item
                            label={copy.catalog.description}
                            span={2}
                          >
                            {selectedKb.description || copy.status.empty}
                          </Descriptions.Item>
                          <Descriptions.Item
                            label={copy.kbManagement.storagePath}
                            span={2}
                          >
                            <Text code>{selectedKb.path}</Text>
                          </Descriptions.Item>
                        </Descriptions>

                        <Card size="small" title={copy.kbManagement.rename}>
                          <Form
                            form={renameForm}
                            layout="vertical"
                            onFinish={(values) => {
                              renameKbMutation.mutate({
                                id: selectedKb.id,
                                name: values.name,
                                description: values.description,
                              });
                            }}
                          >
                            <Row gutter={12}>
                              <Col xs={24} md={10}>
                                <Form.Item
                                  label={copy.chat.knowledgeBaseName}
                                  name="name"
                                  rules={[{ required: true }]}
                                >
                                  <Input />
                                </Form.Item>
                              </Col>
                              <Col xs={24} md={10}>
                                <Form.Item
                                  label={copy.chat.knowledgeBaseDescription}
                                  name="description"
                                >
                                  <Input />
                                </Form.Item>
                              </Col>
                              <Col xs={24} md={4}>
                                <Form.Item label=" ">
                                  <Button
                                    type="primary"
                                    htmlType="submit"
                                    loading={renameKbMutation.isPending}
                                    block
                                  >
                                    {copy.kbManagement.save}
                                  </Button>
                                </Form.Item>
                              </Col>
                            </Row>
                          </Form>
                        </Card>
                      </Space>
                    ),
                  },
                  {
                    key: "files",
                    label: `${copy.kbManagement.filesTab} (${selectedKb.file_count})`,
                    children: (
                      <Space
                        direction="vertical"
                        style={{ width: "100%" }}
                        size="middle"
                      >
                        <Upload
                          accept=".pdf,.doc,.docx,.txt,.md,.xlsx,.pptx"
                          showUploadList={false}
                          beforeUpload={(file) => {
                            uploadFileMutation.mutate({
                              kbId: selectedKb.id,
                              file,
                            });
                            return false;
                          }}
                        >
                          <Button loading={uploadFileMutation.isPending}>
                            {copy.chat.uploadFiles}
                          </Button>
                        </Upload>
                        <Table
                          dataSource={(files.data ?? []) as KnowledgeBaseFile[]}
                          columns={fileColumns}
                          rowKey="id"
                          loading={files.isLoading}
                          size="small"
                          pagination={{ pageSize: 8 }}
                        />
                      </Space>
                    ),
                  },
                  {
                    key: "chunks",
                    label: `${copy.kbManagement.chunksTab} (${stats.data?.chunk_count ?? selectedKb.chunk_count})`,
                    children: (
                      <Space
                        direction="vertical"
                        style={{ width: "100%" }}
                        size="middle"
                      >
                        <Row gutter={[12, 12]}>
                          <Col flex="260px">
                            <Select
                              style={{ width: "100%" }}
                              value={chunkDocumentId ?? ""}
                              options={fileOptions}
                              onChange={(value) => {
                                setChunkDocumentId(value || undefined);
                                setChunkOffset(0);
                              }}
                            />
                          </Col>
                          <Col>
                            <Button
                              onClick={() =>
                                reindexMutation.mutate(selectedKb.id)
                              }
                              loading={reindexMutation.isPending}
                            >
                              {copy.kbManagement.reindex}
                            </Button>
                          </Col>
                        </Row>
                        <Table
                          dataSource={chunks.data?.items ?? []}
                          columns={chunkColumns}
                          rowKey="id"
                          loading={chunks.isLoading}
                          size="small"
                          pagination={{
                            current: Math.floor(chunkOffset / chunkLimit) + 1,
                            pageSize: chunkLimit,
                            total: chunks.data?.total ?? 0,
                            onChange: (page, pageSize) => {
                              const nextLimit = pageSize ?? chunkLimit;
                              setChunkLimit(nextLimit);
                              setChunkOffset((page - 1) * nextLimit);
                            },
                          }}
                        />
                      </Space>
                    ),
                  },
                ]}
              />
            </Card>
          </Col>
        ) : null}
      </Row>

      <CreateKnowledgeBaseModal
        locale={locale}
        open={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
      />
    </Space>
  );
}
