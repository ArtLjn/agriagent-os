import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AdminLayout from './layouts/AdminLayout';
import Crops from './pages/Crops';
import Cycles from './pages/Cycles';
import CycleDetail from './pages/Cycles/Detail';
import Logs from './pages/Logs';
import Costs from './pages/Costs';
import Agent from './pages/Agent';
import Weather from './pages/Weather';
import ApiTester from './pages/ApiTester';
import TraceMonitor from './pages/TraceMonitor';
import TokenDashboard from './pages/TokenDashboard';
import Playground from './pages/Playground';
import SkillRegistry from './pages/SkillRegistry';
import PromptInspector from './pages/PromptInspector';
import ConfigKeys from './pages/ConfigKeys';

export default function App() {
  return (
    <ConfigProvider locale={zhCN} theme={{ algorithm: theme.darkAlgorithm }}>
      <BrowserRouter>
        <AdminLayout>
          <Routes>
            <Route path="/" element={<Navigate to="/dev/traces" replace />} />
            <Route path="/crops" element={<Crops />} />
            <Route path="/cycles" element={<Cycles />} />
            <Route path="/cycles/:id" element={<CycleDetail />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/costs" element={<Costs />} />
            <Route path="/agent" element={<Agent />} />
            <Route path="/weather" element={<Weather />} />
            <Route path="/api-tester" element={<ApiTester />} />
            <Route path="/dev/traces" element={<TraceMonitor />} />
            <Route path="/dev/tokens" element={<TokenDashboard />} />
            <Route path="/dev/playground" element={<Playground />} />
            <Route path="/dev/skills" element={<SkillRegistry />} />
            <Route path="/dev/prompts" element={<PromptInspector />} />
            <Route path="/dev/config" element={<ConfigKeys />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AdminLayout>
      </BrowserRouter>
    </ConfigProvider>
  );
}
