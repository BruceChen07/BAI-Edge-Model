import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Input,
  Progress,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";

import {
  api,
  type DownloadJob,
  type DownloadProgressEvent,
} from "../services/api";
import { messages, type Locale } from "../i18n/messages";

const { Text, Title } = Typography;

const STATUS_COLORS: Record<string, string> = {
  pending: "default",
  downloading: "processing",
  paused: "warning",
  completed: "success",
  failed: "error",
};

export function DownloadPage({ locale }: { locale: Locale }) {
  const copy = messages[locale].downloads;
  const queryClient = useQueryClient();
  const [modelName, setModelName] = useState("qwen3:8b");
  const [source, setSource] = useState("auto");
  const [activeModel, setActiveModel] = useState("qwen3:8b");
  const [progress, setProgress] = useState<DownloadProgressEvent | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const jobsQuery = useQuery({
    queryKey: ["download-jobs"],
    queryFn: () => api.listDownloadJobs(),
    refetchInterval: 2000,
  });

  const planQuery = useQuery({
    queryKey: ["download-plan", modelName, source],
    queryFn: () => api.getDownloadPlan(modelName, source),
    enabled: modelName.trim().length > 0,
  });

  const pullMutation = useMutation({
    mutationFn: () =>
      api.pullModelMultiSource({ model_name: modelName, source }),
    onSuccess: (data) => {
      message.success(`${copy.downloadStarted} ${data.source ?? copy.auto}`);
      setActiveModel(modelName);
      queryClient.invalidateQueries({ queryKey: ["download-jobs"] });
    },
    onError: (err: Error) => {
      message.error(err.message || copy.downloadStartFailed);
    },
  });

  useEffect(() => {
    if (!activeModel) {
      return;
    }

    eventSourceRef.current?.close();
    const es = new EventSource(
      `http://127.0.0.1:8000/api/v1/download/progress/${encodeURIComponent(activeModel)}`,
    );
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as DownloadProgressEvent;
        setProgress(payload);
        queryClient.invalidateQueries({ queryKey: ["download-jobs"] });
      } catch {
        // ignore malformed progress events
      }
    };

    es.onerror = () => {
      es.close();
    };

    return () => {
      es.close();
    };
  }, [activeModel, queryClient]);

  const latestJob = useMemo(() => {
    const items = jobsQuery.data?.items ?? [];
    return (
      items.find((item) => item.model_name === activeModel) ?? items[0] ?? null
    );
  }, [activeModel, jobsQuery.data]);

  const pauseMutation = useMutation({
    mutationFn: (jobId: string) => api.pauseDownloadJob(jobId),
    onSuccess: () => {
      message.success(copy.downloadPaused);
      queryClient.invalidateQueries({ queryKey: ["download-jobs"] });
    },
    onError: (err: Error) => {
      message.error(err.message || copy.pauseFailed);
    },
  });

  const columns = [
    {
      title: copy.model,
      dataIndex: "model_name",
      key: "model_name",
    },
    {
      title: copy.source,
      dataIndex: "source_name",
      key: "source_name",
      render: (value: string) => <Tag>{value || copy.na}</Tag>,
    },
    {
      title: copy.status,
      dataIndex: "status",
      key: "status",
      render: (value: string) => (
        <Tag color={STATUS_COLORS[value] ?? "default"}>{value}</Tag>
      ),
    },
    {
      title: copy.progress,
      key: "progress",
      render: (_: unknown, row: DownloadJob) => {
        const percent =
          row.total_bytes > 0
            ? Math.round((row.downloaded_bytes / row.total_bytes) * 100)
            : 0;
        return <Progress percent={percent} size="small" />;
      },
    },
    {
      title: copy.action,
      key: "action",
      render: (_: unknown, row: DownloadJob) => (
        <Button
          size="small"
          disabled={row.status !== "downloading"}
          onClick={() => pauseMutation.mutate(row.id)}
        >
          {copy.pause}
        </Button>
      ),
    },
  ];

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Card>
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <Title level={4} style={{ margin: 0 }}>
            {copy.pageTitle}
          </Title>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={10}>
              <Input
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                placeholder={copy.modelPlaceholder}
              />
            </Col>
            <Col xs={24} md={6}>
              <Select
                value={source}
                onChange={setSource}
                style={{ width: "100%" }}
                options={[
                  { label: copy.auto, value: "auto" },
                  { label: copy.ollama, value: "ollama" },
                  { label: copy.huggingFace, value: "huggingface" },
                  { label: copy.modelScope, value: "modelscope" },
                ]}
              />
            </Col>
            <Col xs={24} md={8}>
              <Space>
                <Button
                  type="primary"
                  loading={pullMutation.isPending}
                  onClick={() => pullMutation.mutate()}
                >
                  {copy.startDownload}
                </Button>
                <Button onClick={() => jobsQuery.refetch()}>
                  {copy.refreshJobs}
                </Button>
              </Space>
            </Col>
          </Row>

          {planQuery.data && (
            <Alert
              type="info"
              showIcon
              message={`${copy.resolvedPlan} ${planQuery.data.model_name}`}
              description={
                <Space wrap>
                  {planQuery.data.sources.map((item) => (
                    <Tag key={`${item.name}-${item.priority}`}>
                      {item.priority}.{item.name}
                    </Tag>
                  ))}
                </Space>
              }
            />
          )}
        </Space>
      </Card>

      <Card title={copy.liveProgress}>
        {progress ? (
          <Space direction="vertical" style={{ width: "100%" }}>
            <Text>
              <strong>{copy.model}:</strong> {progress.model_name}
            </Text>
            <Text>
              <strong>{copy.source}:</strong> {progress.source_name || copy.na}
            </Text>
            <Progress
              percent={Math.round(progress.percent)}
              status={progress.status === "failed" ? "exception" : undefined}
            />
            <Text>
              <strong>{copy.speed}:</strong> {progress.speed_mbps} MB/s
            </Text>
            <Text>
              <strong>{copy.eta}:</strong> {progress.eta_seconds}s
            </Text>
            {progress.error ? (
              <Alert type="error" showIcon message={progress.error} />
            ) : null}
          </Space>
        ) : (
          <Text type="secondary">{copy.noActiveProgress}</Text>
        )}
      </Card>

      <Card title={copy.latestJob}>
        {latestJob ? (
          <Space direction="vertical" style={{ width: "100%" }}>
            <Text>
              <strong>ID:</strong> {latestJob.id}
            </Text>
            <Text>
              <strong>{copy.status}:</strong> {latestJob.status}
            </Text>
            <Text>
              <strong>{copy.output}:</strong> {latestJob.output_path}
            </Text>
            <Text>
              <strong>{copy.retries}:</strong> {latestJob.retry_count}/
              {latestJob.max_retries}
            </Text>
          </Space>
        ) : (
          <Text type="secondary">{copy.noJobsYet}</Text>
        )}
      </Card>

      <Card title={copy.downloadJobs}>
        <Table<DownloadJob>
          rowKey="id"
          dataSource={jobsQuery.data?.items ?? []}
          columns={columns}
          loading={jobsQuery.isLoading}
          pagination={{ pageSize: 10 }}
        />
      </Card>
    </Space>
  );
}
