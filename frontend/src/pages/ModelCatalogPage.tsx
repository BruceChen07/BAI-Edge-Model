import { useMemo, useState } from "react";
import {
  Card,
  Col,
  Input,
  Modal,
  Progress,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  Button,
  message,
  Descriptions,
  Slider,
} from "antd";
import {
  SearchOutlined,
  ReloadOutlined,
  InfoCircleOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";

import { api, type CatalogEntry } from "../services/api";
import { messages, type Locale } from "../i18n/messages";

const { Text, Title } = Typography;

const FIT_COLORS: Record<string, string> = {
  perfect: "#52c41a",
  good: "#1890ff",
  marginal: "#faad14",
  too_tight: "#ff4d4f",
  unknown: "#d9d9d9",
};

const MODE_COLORS: Record<string, string> = {
  GPU: "#722ed1",
  "CPU+GPU": "#2f54eb",
  CPU: "#13c2c2",
  MoE: "#eb2f96",
};

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <Space direction="vertical" size={0} style={{ width: "100%" }}>
      <Text type="secondary" style={{ fontSize: 11 }}>
        {label}
      </Text>
      <Progress
        percent={value}
        size="small"
        strokeColor={
          value >= 80 ? "#52c41a" : value >= 60 ? "#1890ff" : "#faad14"
        }
        format={() => `${Math.round(value)}`}
      />
    </Space>
  );
}

function ModelDetailModal({
  entry,
  open,
  onClose,
  locale,
}: {
  entry: CatalogEntry | null;
  open: boolean;
  onClose: () => void;
  locale: Locale;
}) {
  if (!entry) return null;
  const copy = messages[locale].catalog;

  const scores = [
    { label: copy.quality, value: entry.score_quality },
    { label: copy.speed, value: entry.score_speed },
    { label: copy.fit, value: entry.score_fit },
    { label: copy.contextScore, value: entry.score_context },
  ];

  return (
    <Modal
      title={
        <Space>
          <Text strong style={{ fontSize: 16 }}>
            {entry.model_name}
          </Text>
          <Tag color={FIT_COLORS[entry.fit_level] ?? "#d9d9d9"}>
            {entry.fit_level}
          </Tag>
        </Space>
      }
      open={open}
      onCancel={onClose}
      footer={null}
      width={640}
    >
      <Descriptions
        column={2}
        size="small"
        bordered
        style={{ marginBottom: 16 }}
      >
        <Descriptions.Item label={copy.provider}>
          {entry.provider}
        </Descriptions.Item>
        <Descriptions.Item label={copy.paramSize}>
          {entry.param_size}
        </Descriptions.Item>
        <Descriptions.Item label={copy.runMode}>
          <Tag color={MODE_COLORS[entry.run_mode] ?? "#d9d9d9"}>
            {entry.run_mode}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label={copy.quantization}>
          {entry.quantization}
        </Descriptions.Item>
        <Descriptions.Item label={copy.memoryRequired}>
          {entry.memory_required_gb} GB
        </Descriptions.Item>
        <Descriptions.Item label={copy.vramRequired}>
          {entry.vram_required_gb > 0
            ? `${entry.vram_required_gb} GB`
            : copy.notAvailable}
        </Descriptions.Item>
        <Descriptions.Item label={copy.estTps}>
          {entry.estimated_tps}
        </Descriptions.Item>
        <Descriptions.Item label={copy.maxContext}>
          {(entry.max_context / 1024).toFixed(0)}K
        </Descriptions.Item>
        <Descriptions.Item label={copy.useCase}>
          {entry.use_case}
        </Descriptions.Item>
        <Descriptions.Item label={copy.moe}>
          {entry.is_moe ? <Tag color="purple">{copy.yes}</Tag> : copy.no}
        </Descriptions.Item>
        <Descriptions.Item label={copy.available}>
          {entry.available ? (
            <Tag color="green">{copy.installed}</Tag>
          ) : (
            <Tag color="default">{copy.notInstalled}</Tag>
          )}
        </Descriptions.Item>
        <Descriptions.Item label={copy.source}>
          {entry.source}
        </Descriptions.Item>
      </Descriptions>

      <Title level={5} style={{ marginTop: 0 }}>
        {copy.scores}
      </Title>
      <Row gutter={[8, 8]}>
        <Col span={12}>
          <Card size="small">
            <StatScore label={copy.total} value={entry.score_total} />
          </Card>
        </Col>
        {scores.map((s) => (
          <Col span={12} key={s.label}>
            <Card size="small">
              <ScoreBar label={s.label} value={s.value} />
            </Card>
          </Col>
        ))}
      </Row>

      {entry.description && (
        <>
          <Title level={5}>{copy.description}</Title>
          <Text>{entry.description}</Text>
        </>
      )}

      {entry.tags.length > 0 && (
        <>
          <Title level={5}>{copy.tags}</Title>
          <Space wrap>
            {entry.tags.map((t) => (
              <Tag key={t}>{t}</Tag>
            ))}
          </Space>
        </>
      )}
    </Modal>
  );
}

function StatScore({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ textAlign: "center" }}>
      <Text type="secondary" style={{ fontSize: 11 }}>
        {label}
      </Text>
      <div>
        <Text
          strong
          style={{
            fontSize: 24,
            color:
              value >= 80 ? "#52c41a" : value >= 60 ? "#1890ff" : "#faad14",
          }}
        >
          {Math.round(value)}
        </Text>
      </div>
    </div>
  );
}

export function ModelCatalogPage({ locale }: { locale: Locale }) {
  const copy = messages[locale].catalog;
  const [searchText, setSearchText] = useState("");
  const [providerFilter, setProviderFilter] = useState<string | undefined>();
  const [fitFilter, setFitFilter] = useState<string | undefined>();
  const [minScore, setMinScore] = useState<number>(0);
  const [detailEntry, setDetailEntry] = useState<CatalogEntry | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const { data, isLoading, refetch } = useQuery({
    queryKey: [
      "catalog-list",
      {
        provider: providerFilter,
        fit_level: fitFilter,
        min_score: minScore || undefined,
      },
    ],
    queryFn: () =>
      api.catalogList({
        provider: providerFilter,
        fit_level: fitFilter,
        min_score: minScore > 0 ? minScore : undefined,
        limit: 100,
      }),
  });

  const localModels = useQuery({
    queryKey: ["local-models"],
    queryFn: api.getModels,
  });

  const searchQuery = useQuery({
    queryKey: ["catalog-search", searchText],
    queryFn: () => api.catalogSearch(searchText),
    enabled: searchText.length > 0,
  });

  const items = useMemo(() => {
    const local = localModels.data ?? [];
    const localNames = new Set(local.map((m) => m.name));

    const baseItems =
      (searchText ? searchQuery.data?.items : data?.items) ?? [];
    const merged = baseItems.map((entry) => ({
      ...entry,
      available: entry.available || localNames.has(entry.model_name),
    }));

    const known = new Set(merged.map((i) => i.model_name));
    const localOnly = local
      .filter((m) => !known.has(m.name))
      .map((m) => ({
        id: `local:${m.name}`,
        model_name: m.name,
        provider: inferProvider(m.name),
        param_size: extractParamSize(m.name),
        version: "",
        score_total: 0,
        score_quality: 0,
        score_speed: 0,
        score_fit: 0,
        score_context: 0,
        fit_level: "unknown",
        estimated_tps: 0,
        quantization: inferQuantization(m.name),
        memory_required_gb: 0,
        vram_required_gb: 0,
        run_mode: "CPU",
        use_case: "general",
        max_context: 8192,
        is_moe: false,
        available: true,
        description: "",
        tags: [],
        source: "local",
        raw_json: "",
        last_synced_at: "",
        created_at: "",
        updated_at: "",
      })) as unknown as CatalogEntry[];

    const combined = [...merged, ...localOnly];
    const filtered = combined.filter((entry) => {
      if (providerFilter && entry.provider !== providerFilter) return false;
      if (fitFilter && entry.fit_level !== fitFilter) return false;
      if (minScore > 0 && entry.score_total < minScore) return false;
      if (searchText) {
        const q = searchText.toLowerCase();
        return (
          entry.model_name.toLowerCase().includes(q) ||
          entry.provider.toLowerCase().includes(q) ||
          entry.param_size.toLowerCase().includes(q) ||
          entry.source.toLowerCase().includes(q)
        );
      }
      return true;
    });
    filtered.sort((a, b) => (b.score_total ?? 0) - (a.score_total ?? 0));
    return filtered;
  }, [
    data?.items,
    fitFilter,
    localModels.data,
    minScore,
    providerFilter,
    searchQuery.data?.items,
    searchText,
  ]);

  const total = items.length;

  const localModelCount = localModels.data?.length ?? 0;
  const catalogCount = data?.total ?? data?.items?.length ?? 0;
  const localMissingCount = useMemo(() => {
    const local = localModels.data ?? [];
    const catalogItems = data?.items ?? [];
    const catalogNames = new Set(catalogItems.map((i) => i.model_name));
    let missing = 0;
    for (const model of local) {
      if (!catalogNames.has(model.name)) {
        missing += 1;
      }
    }
    return missing;
  }, [data?.items, localModels.data]);

  const handleSync = async () => {
    try {
      const res = await api.catalogSync("curated");
      message.success(res.message);
      refetch();
    } catch {
      message.error(copy.syncFailed);
    }
  };

  const handleSyncLocal = async () => {
    try {
      const res = await api.catalogSync("local");
      message.success(res.message);
      refetch();
      localModels.refetch();
    } catch {
      message.error(copy.syncFailed);
    }
  };

  const handleDetail = (entry: CatalogEntry) => {
    setDetailEntry(entry);
    setModalOpen(true);
  };

  const columns = [
    {
      title: copy.model,
      dataIndex: "model_name",
      key: "model_name",
      width: 180,
      render: (_: unknown, r: CatalogEntry) => (
        <Space>
          <Text strong>{r.model_name}</Text>
          <Tag
            color={FIT_COLORS[r.fit_level] ?? "#d9d9d9"}
            style={{ fontSize: 10 }}
          >
            {r.fit_level}
          </Tag>
        </Space>
      ),
    },
    {
      title: copy.provider,
      dataIndex: "provider",
      key: "provider",
      width: 80,
    },
    {
      title: copy.size,
      dataIndex: "param_size",
      key: "param_size",
      width: 70,
    },
    {
      title: copy.score,
      dataIndex: "score_total",
      key: "score_total",
      width: 100,
      sorter: (a: CatalogEntry, b: CatalogEntry) =>
        a.score_total - b.score_total,
      defaultSortOrder: "descend" as const,
      render: (v: number) => (
        <Progress
          percent={v}
          size="small"
          strokeColor={v >= 80 ? "#52c41a" : v >= 60 ? "#1890ff" : "#faad14"}
          format={() => `${Math.round(v)}`}
        />
      ),
    },
    {
      title: copy.tps,
      dataIndex: "estimated_tps",
      key: "estimated_tps",
      width: 70,
      render: (v: number) => `${v}`,
    },
    {
      title: copy.mode,
      dataIndex: "run_mode",
      key: "run_mode",
      width: 90,
      render: (v: string) => <Tag color={MODE_COLORS[v] ?? "#d9d9d9"}>{v}</Tag>,
    },
    {
      title: copy.memory,
      dataIndex: "memory_required_gb",
      key: "memory_required_gb",
      width: 80,
      render: (v: number) => `${v} GB`,
    },
    {
      title: copy.context,
      dataIndex: "max_context",
      key: "max_context",
      width: 80,
      render: (v: number) => `${(v / 1024).toFixed(0)}K`,
    },
    {
      title: copy.source,
      dataIndex: "source",
      key: "source",
      width: 80,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: "",
      key: "action",
      width: 50,
      render: (_: unknown, r: CatalogEntry) => (
        <Button
          type="text"
          size="small"
          icon={<InfoCircleOutlined />}
          onClick={() => handleDetail(r)}
        />
      ),
    },
  ];

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="middle">
      <Row gutter={[16, 8]} align="middle">
        <Col xs={24} sm={8}>
          <Input
            prefix={<SearchOutlined />}
            placeholder={copy.searchPlaceholder}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            allowClear
          />
        </Col>
        <Col xs={12} sm={4}>
          <Select
            placeholder={copy.providerPlaceholder}
            value={providerFilter}
            onChange={setProviderFilter}
            allowClear
            style={{ width: "100%" }}
            options={[
              { label: "Qwen", value: "Qwen" },
              { label: "Meta", value: "Meta" },
              { label: "Google", value: "Google" },
              { label: "Microsoft", value: "Microsoft" },
              { label: "DeepSeek", value: "DeepSeek" },
            ]}
          />
        </Col>
        <Col xs={12} sm={4}>
          <Select
            placeholder={copy.fitPlaceholder}
            value={fitFilter}
            onChange={setFitFilter}
            allowClear
            style={{ width: "100%" }}
            options={[
              { label: "Perfect", value: "perfect" },
              { label: "Good", value: "good" },
              { label: "Marginal", value: "marginal" },
              { label: "Too Tight", value: "too_tight" },
            ]}
          />
        </Col>
        <Col xs={12} sm={4}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {copy.minScore}: {minScore}
          </Text>
          <Slider
            min={0}
            max={100}
            value={minScore}
            onChange={setMinScore}
            tooltip={{ formatter: (v) => `${v}` }}
          />
        </Col>
        <Col xs={12} sm={4}>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => refetch()}>
              {copy.refresh}
            </Button>
            <Button onClick={handleSyncLocal}>{copy.syncLocal}</Button>
            <Button onClick={handleSync}>{copy.syncCatalog}</Button>
          </Space>
        </Col>
      </Row>

      <Card size="small">
        <Text type="secondary">
          {copy.localDetected}: {localModelCount} · {copy.catalogDetected}:{" "}
          {catalogCount} · {copy.showing}: {total}
          {localMissingCount > 0
            ? ` · ${copy.localOnlyHint.replace("{n}", String(localMissingCount))}`
            : ""}
        </Text>
      </Card>

      <Table<CatalogEntry>
        dataSource={items ?? []}
        columns={columns}
        rowKey="id"
        loading={isLoading || searchQuery.isLoading || localModels.isLoading}
        size="small"
        pagination={{
          pageSize: 20,
          showSizeChanger: true,
          showTotal: (t) => `${t} models`,
        }}
        scroll={{ x: 900 }}
      />

      <ModelDetailModal
        entry={detailEntry}
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        locale={locale}
      />
    </Space>
  );
}

function inferProvider(modelName: string) {
  const name = modelName.toLowerCase();
  if (name.startsWith("qwen")) return "Qwen";
  if (name.startsWith("llama")) return "Meta";
  if (name.startsWith("gemma")) return "Google";
  if (name.startsWith("phi")) return "Microsoft";
  if (name.startsWith("deepseek")) return "DeepSeek";
  return "unknown";
}

function extractParamSize(modelName: string) {
  const match = modelName.toLowerCase().match(/[:|\\-_]?(\\d+\\.?\\d*)b/);
  if (match?.[1]) {
    return `${match[1]}B`;
  }
  return "unknown";
}

function inferQuantization(modelName: string) {
  const lowered = modelName.toLowerCase();
  for (const token of ["q2", "q3", "q4", "q5", "q6", "q8"]) {
    if (lowered.includes(token)) return token.toUpperCase();
  }
  return "Q4_K_M";
}
