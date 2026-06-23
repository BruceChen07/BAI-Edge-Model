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

const TERMINAL_STATUSES = new Set(["completed", "failed", "paused"]);
const API_BASE = "http://127.0.0.1:8000/api/v1";

function isTerminalStatus(status: string): boolean {
  return TERMINAL_STATUSES.has(status);
}

function getJobPercent(job: DownloadJob | null): number {
  if (!job || job.total_bytes <= 0) {
    return 0;
  }
  return Math.round((job.downloaded_bytes / job.total_bytes) * 100);
}

function formatBytes(value: number): string {
  if (!value) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function buildProgressFromJob(
  job: DownloadJob | null,
): DownloadProgressEvent | null {
  if (!job) {
    return null;
  }
  return {
    job_id: job.id,
    model_name: job.model_name,
    status: job.status,
    downloaded_bytes: job.downloaded_bytes,
    total_bytes: job.total_bytes,
    percent: getJobPercent(job),
    speed_mbps: 0,
    eta_seconds: 0,
    source_name: job.source_name,
    error: job.error_message,
  };
}

export function DownloadPage({ locale }: { locale: Locale }) {
  const copy = messages[locale].downloads;
  const queryClient = useQueryClient();
  const [modelName, setModelName] = useState("qwen3:8b");
  const [source, setSource] = useState("auto");
  const [activeModel, setActiveModel] = useState("qwen3:8b");
  const [activeJobId, setActiveJobId] = useState("");
  const [selectedJobId, setSelectedJobId] = useState("");
  const [progress, setProgress] = useState<DownloadProgressEvent | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const jobsQuery = useQuery({
    queryKey: ["download-jobs"],
    queryFn: () => api.listDownloadJobs(),
    refetchInterval: 2000,
  });

  const jobs = useMemo(
    () => jobsQuery.data?.items ?? [],
    [jobsQuery.data?.items],
  );
  const fallbackActiveJobId =
    jobs.find((job) => !isTerminalStatus(job.status))?.id ?? "";
  const currentActiveJobId = activeJobId || fallbackActiveJobId;
  const resolvedSelectedJobId =
    (selectedJobId && jobs.some((job) => job.id === selectedJobId)
      ? selectedJobId
      : "") ||
    currentActiveJobId ||
    jobs.find((job) => job.model_name === activeModel)?.id ||
    jobs[0]?.id ||
    "";

  const jobDetailQuery = useQuery({
    queryKey: ["download-job", resolvedSelectedJobId],
    queryFn: () => api.getDownloadJob(resolvedSelectedJobId),
    enabled: resolvedSelectedJobId.length > 0,
    refetchInterval: ({ state }) => {
      const job = state.data as DownloadJob | undefined;
      if (!job || !isTerminalStatus(job.status)) {
        return 2000;
      }
      return false;
    },
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
      const nextJobId = data.job_id ?? "";
      message.success(`${copy.downloadStarted} ${data.source ?? copy.auto}`);
      setActiveModel(modelName);
      setActiveJobId(nextJobId);
      setSelectedJobId(nextJobId);
      setProgress(null);
      queryClient.invalidateQueries({ queryKey: ["download-jobs"] });
      if (nextJobId) {
        queryClient.invalidateQueries({
          queryKey: ["download-job", nextJobId],
        });
      }
    },
    onError: (err: Error) => {
      message.error(err.message || copy.downloadStartFailed);
    },
  });

  useEffect(() => {
    if (!currentActiveJobId) {
      eventSourceRef.current?.close();
      return;
    }

    eventSourceRef.current?.close();
    const es = new EventSource(
      `${API_BASE}/download/jobs/${encodeURIComponent(currentActiveJobId)}/progress`,
    );
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as DownloadProgressEvent;
        setProgress(payload);
        if (payload.job_id) {
          setSelectedJobId(payload.job_id);
          queryClient.invalidateQueries({
            queryKey: ["download-job", payload.job_id],
          });
        }
        queryClient.invalidateQueries({ queryKey: ["download-jobs"] });
        if (isTerminalStatus(payload.status)) {
          setActiveJobId((current) =>
            current === payload.job_id ? "" : current,
          );
        }
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
  }, [currentActiveJobId, queryClient]);

  const selectedJob = useMemo(() => {
    return (
      jobDetailQuery.data ??
      jobs.find((item) => item.id === resolvedSelectedJobId) ??
      jobs.find((item) => item.model_name === activeModel) ??
      jobs[0] ??
      null
    );
  }, [activeModel, jobDetailQuery.data, jobs, resolvedSelectedJobId]);

  const displayProgress = useMemo(() => {
    if (progress && (!selectedJob || progress.job_id === selectedJob.id)) {
      return progress;
    }
    return buildProgressFromJob(selectedJob);
  }, [progress, selectedJob]);

  const pauseMutation = useMutation({
    mutationFn: (jobId: string) => api.pauseDownloadJob(jobId),
    onSuccess: (_, jobId) => {
      message.success(copy.downloadPaused);
      setActiveJobId((current) => (current === jobId ? "" : current));
      queryClient.invalidateQueries({ queryKey: ["download-jobs"] });
      queryClient.invalidateQueries({ queryKey: ["download-job", jobId] });
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
      render: (_: unknown, row: DownloadJob) => (
        <Progress percent={getJobPercent(row)} size="small" />
      ),
    },
    {
      title: copy.action,
      key: "action",
      render: (_: unknown, row: DownloadJob) => (
        <Button
          size="small"
          disabled={row.status !== "downloading"}
          onClick={(event) => {
            event.stopPropagation();
            pauseMutation.mutate(row.id);
          }}
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
        {displayProgress ? (
          <Space direction="vertical" style={{ width: "100%" }}>
            <Text>
              <strong>ID:</strong> {displayProgress.job_id || copy.na}
            </Text>
            <Text>
              <strong>{copy.model}:</strong> {displayProgress.model_name}
            </Text>
            <Text>
              <strong>{copy.source}:</strong>{" "}
              {displayProgress.source_name || copy.na}
            </Text>
            <Progress
              percent={Math.round(displayProgress.percent)}
              status={
                displayProgress.status === "failed" ? "exception" : undefined
              }
            />
            <Text>
              <strong>{copy.speed}:</strong> {displayProgress.speed_mbps} MB/s
            </Text>
            <Text>
              <strong>{copy.eta}:</strong> {displayProgress.eta_seconds}s
            </Text>
            {displayProgress.error ? (
              <Alert type="error" showIcon message={displayProgress.error} />
            ) : null}
          </Space>
        ) : (
          <Text type="secondary">{copy.noActiveProgress}</Text>
        )}
      </Card>

      <Card title={copy.jobDetail}>
        {selectedJob ? (
          <Space direction="vertical" style={{ width: "100%" }}>
            <Text>
              <strong>ID:</strong> {selectedJob.id}
            </Text>
            <Text>
              <strong>{copy.model}:</strong> {selectedJob.model_name}
            </Text>
            <Text>
              <strong>{copy.source}:</strong>{" "}
              {selectedJob.source_name || copy.na}
            </Text>
            <Text>
              <strong>{copy.status}:</strong> {selectedJob.status}
            </Text>
            <Text>
              <strong>{copy.progress}:</strong> {getJobPercent(selectedJob)}%
            </Text>
            <Text>
              <strong>{copy.downloaded}:</strong>{" "}
              {formatBytes(selectedJob.downloaded_bytes)}
            </Text>
            <Text>
              <strong>{copy.total}:</strong>{" "}
              {selectedJob.total_bytes > 0
                ? formatBytes(selectedJob.total_bytes)
                : copy.na}
            </Text>
            <Text>
              <strong>{copy.output}:</strong>{" "}
              {selectedJob.output_path || copy.na}
            </Text>
            <Text>
              <strong>{copy.retries}:</strong> {selectedJob.retry_count}/
              {selectedJob.max_retries}
            </Text>
            <Text>
              <strong>{copy.startedAt}:</strong>{" "}
              {selectedJob.started_at || copy.na}
            </Text>
            <Text>
              <strong>{copy.lastProgress}:</strong>{" "}
              {selectedJob.last_progress_at || copy.na}
            </Text>
            <Text>
              <strong>{copy.completedAt}:</strong>{" "}
              {selectedJob.completed_at || copy.na}
            </Text>
            {selectedJob.error_message ? (
              <Alert
                type="error"
                showIcon
                message={`${copy.error}: ${selectedJob.error_message}`}
              />
            ) : null}
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
          onRow={(row) => ({
            onClick: () => {
              setSelectedJobId(row.id);
              if (!isTerminalStatus(row.status)) {
                setActiveJobId(row.id);
              }
            },
          })}
        />
      </Card>
    </Space>
  );
}
