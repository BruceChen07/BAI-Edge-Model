import { useMemo } from "react";
import { Card, Col, Row, Space, Statistic, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";

import { messages, type Locale } from "../i18n/messages";
import { api } from "../services/api";

const { Text } = Typography;

type AdminPageProps = {
  locale: Locale;
};

export function AdminPage({ locale }: AdminPageProps) {
  const copy = messages[locale];

  const systemInfo = useQuery({
    queryKey: ["system-info"],
    queryFn: api.getSystemInfo,
  });
  const knowledgeBases = useQuery({
    queryKey: ["knowledge-bases"],
    queryFn: api.listKnowledgeBases,
  });
  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: api.listSessions,
  });
  const tasks = useQuery({
    queryKey: ["tasks"],
    queryFn: api.listTasks,
  });
  const memories = useQuery({
    queryKey: ["memories"],
    queryFn: api.listMemories,
  });
  const models = useQuery({
    queryKey: ["models"],
    queryFn: api.getModels,
  });

  const stats = useMemo(
    () => [
      {
        title: copy.panels.knowledgeBases,
        value: knowledgeBases.data?.length ?? 0,
      },
      {
        title: copy.panels.sessions,
        value: sessions.data?.length ?? 0,
      },
      {
        title: copy.panels.tasks,
        value: tasks.data?.length ?? 0,
      },
      {
        title: copy.panels.models,
        value: models.data?.length ?? 0,
      },
    ],
    [copy, knowledgeBases.data, models.data, sessions.data, tasks.data],
  );

  const renderList = (items: Array<Record<string, unknown>> | undefined) => {
    if (!items || items.length === 0) {
      return <Text type="secondary">{copy.status.empty}</Text>;
    }

    return (
      <Space direction="vertical" style={{ width: "100%" }}>
        {items.slice(0, 5).map((item, index) => (
          <Card key={`${index}-${String(item.id ?? item.title ?? "item")}`} size="small">
            <Space direction="vertical" size={4}>
              {Object.entries(item)
                .slice(0, 4)
                .map(([key, value]) => (
                  <Text key={key}>
                    <strong>{key}:</strong> {String(value)}
                  </Text>
                ))}
            </Space>
          </Card>
        ))}
      </Space>
    );
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Row gutter={[16, 16]}>
        {stats.map((item) => (
          <Col key={item.title} xs={24} sm={12} lg={6}>
            <Card>
              <Statistic title={item.title} value={item.value} />
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={8}>
          <Card title={copy.panels.system}>
            <Space direction="vertical" style={{ width: "100%" }}>
              <Text>
                <strong>app_name:</strong>{" "}
                {String(systemInfo.data?.app_name ?? copy.status.loading)}
              </Text>
              <Text>
                <strong>version:</strong>{" "}
                {String(systemInfo.data?.version ?? copy.status.loading)}
              </Text>
              <Text>
                <strong>storage_root:</strong>{" "}
                {String(
                  (systemInfo.data?.runtime as Record<string, unknown> | undefined)?.storage_root ??
                    copy.status.loading,
                )}
              </Text>
              <Text>
                <strong>ollama_models:</strong> {models.data?.length ?? 0}
              </Text>
              <Text>
                <strong>memories:</strong> {memories.data?.length ?? 0}
              </Text>
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          <Card title={copy.panels.models}>
            {renderList((models.data ?? []) as Array<Record<string, unknown>>)}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card title={copy.panels.knowledgeBases}>
            {renderList(knowledgeBases.data)}
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card title={copy.panels.sessions}>
            {renderList(sessions.data as Array<Record<string, unknown>>)}
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card title={copy.panels.tasks}>{renderList(tasks.data)}</Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card title={copy.panels.memories}>{renderList(memories.data)}</Card>
        </Col>
      </Row>
    </Space>
  );
}
