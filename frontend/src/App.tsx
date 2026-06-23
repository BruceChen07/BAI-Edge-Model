import { useState } from "react";
import {
  App as AntdApp,
  Button,
  Layout,
  Segmented,
  Space,
  Typography,
} from "antd";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";

import { messages, type Locale } from "./i18n/messages";
import { ChatPage } from "./pages/ChatPage";
import { AdminPage } from "./pages/AdminPage";
import { KnowledgeBaseManagePage } from "./pages/KnowledgeBaseManagePage";
import { ModelCatalogPage } from "./pages/ModelCatalogPage";
import { DownloadPage } from "./pages/DownloadPage";
import { MarkdownStudioPage } from "./pages/MarkdownStudioPage";

const { Header, Content } = Layout;
const { Paragraph, Title } = Typography;

function App() {
  const [locale, setLocale] = useState<Locale>("zh-CN");
  const copy = messages[locale];

  return (
    <AntdApp>
      <Layout className="app-shell">
        <Header className="app-header">
          <div>
            <Title level={3} style={{ margin: 0, color: "#fff" }}>
              {copy.title}
            </Title>
            <Paragraph style={{ margin: 0, color: "rgba(255,255,255,0.75)" }}>
              {copy.subtitle}
            </Paragraph>
          </div>
          <Space>
            <NavLink to="/">
              {({ isActive }) => (
                <Button type={isActive ? "primary" : "default"}>
                  {copy.navigation.home}
                </Button>
              )}
            </NavLink>
            <NavLink to="/admin">
              {({ isActive }) => (
                <Button type={isActive ? "primary" : "default"}>
                  {copy.navigation.admin}
                </Button>
              )}
            </NavLink>
            <NavLink to="/catalog">
              {({ isActive }) => (
                <Button type={isActive ? "primary" : "default"}>
                  {copy.navigation.catalog}
                </Button>
              )}
            </NavLink>
            <NavLink to="/downloads">
              {({ isActive }) => (
                <Button type={isActive ? "primary" : "default"}>
                  {copy.navigation.downloads}
                </Button>
              )}
            </NavLink>
            <NavLink to="/knowledge-bases">
              {({ isActive }) => (
                <Button type={isActive ? "primary" : "default"}>
                  {copy.navigation.knowledgeBases}
                </Button>
              )}
            </NavLink>
            <NavLink to="/markdown-studio">
              {({ isActive }) => (
                <Button type={isActive ? "primary" : "default"}>
                  {copy.navigation.markdownStudio}
                </Button>
              )}
            </NavLink>
            <Segmented<Locale>
              value={locale}
              options={[
                { label: "中文", value: "zh-CN" },
                { label: "English", value: "en-US" },
              ]}
              onChange={(value) => setLocale(value)}
            />
          </Space>
        </Header>
        <Content className="app-content">
          <Routes>
            <Route path="/" element={<ChatPage locale={locale} />} />
            <Route path="/admin" element={<AdminPage locale={locale} />} />
            <Route
              path="/catalog"
              element={<ModelCatalogPage locale={locale} />}
            />
            <Route
              path="/downloads"
              element={<DownloadPage locale={locale} />}
            />
            <Route
              path="/knowledge-bases"
              element={<KnowledgeBaseManagePage locale={locale} />}
            />
            <Route
              path="/markdown-studio"
              element={<MarkdownStudioPage locale={locale} />}
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Content>
      </Layout>
    </AntdApp>
  );
}

export default App;
