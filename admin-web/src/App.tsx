import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AdminLayout from './layouts/AdminLayout';
import Crops from './pages/Crops';
import Cycles from './pages/Cycles';
import CycleDetail from './pages/Cycles/Detail';
import Logs from './pages/Logs';
import Costs from './pages/Costs';
import Dashboard from './pages/Dashboard';
import Agent from './pages/Agent';
import Weather from './pages/Weather';
import TraceMonitor from './pages/TraceMonitor';
import TokenDashboard from './pages/TokenDashboard';
import Playground from './pages/Playground';
import DataFlywheel from './pages/DataFlywheel';
import SkillRegistry from './pages/SkillRegistry';
import PromptInspector from './pages/PromptInspector';
import ConfigKeys from './pages/ConfigKeys';
import Simulation from './pages/Simulation';
import Users from './pages/Users';
import Operations from './pages/Operations';
import Login from './pages/Login';
import { authStore } from './stores/authStore';
import { palette, layout } from './styles/theme';

function AuthGuard({ children }: { children: React.ReactNode }) {
  if (!authStore.isLoggedIn()) {
    return <Navigate to="/login" replace />;
  }
  return <AdminLayout>{children}</AdminLayout>;
}

export default function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: palette.accentStrong,
          colorBgBase: palette.bg,
          colorBgContainer: palette.bgElevated,
          colorBgElevated: palette.bgPanel,
          colorBorder: palette.border,
          colorText: palette.text,
          colorTextSecondary: palette.textMuted,
          borderRadius: layout.radius,
          fontSize: 14,
          controlHeight: 34,
        },
        components: {
          Button: {
            borderRadius: layout.radius,
            controlHeight: 34,
          },
          Card: {
            borderRadiusLG: layout.radius,
            headerBg: palette.bgElevated,
          },
          Input: {
            activeBorderColor: palette.accent,
            hoverBorderColor: palette.accent,
          },
          Select: {
            optionSelectedBg: 'rgba(88, 166, 255, 0.16)',
          },
          Table: {
            headerBg: palette.bgElevated,
            rowHoverBg: 'rgba(88, 166, 255, 0.06)',
          },
        },
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login onLogin={() => window.location.href = '/'} />} />
          <Route path="/" element={<AuthGuard><Navigate to="/dashboard" replace /></AuthGuard>} />
          <Route path="/dashboard" element={<AuthGuard><Dashboard /></AuthGuard>} />
          <Route path="/users" element={<AuthGuard><Users /></AuthGuard>} />
          <Route path="/operations" element={<AuthGuard><Operations /></AuthGuard>} />
          <Route path="/crops" element={<AuthGuard><Crops /></AuthGuard>} />
          <Route path="/cycles" element={<AuthGuard><Cycles /></AuthGuard>} />
          <Route path="/cycles/:id" element={<AuthGuard><CycleDetail /></AuthGuard>} />
          <Route path="/logs" element={<AuthGuard><Logs /></AuthGuard>} />
          <Route path="/costs" element={<AuthGuard><Costs /></AuthGuard>} />
          <Route path="/agent" element={<AuthGuard><Agent /></AuthGuard>} />
          <Route path="/weather" element={<AuthGuard><Weather /></AuthGuard>} />
          <Route path="/dev/traces" element={<AuthGuard><TraceMonitor /></AuthGuard>} />
          <Route path="/dev/tokens" element={<AuthGuard><TokenDashboard /></AuthGuard>} />
          <Route path="/dev/playground" element={<AuthGuard><Playground /></AuthGuard>} />
          <Route path="/dev/data-flywheel" element={<AuthGuard><DataFlywheel /></AuthGuard>} />
          <Route path="/dev/skills" element={<AuthGuard><SkillRegistry /></AuthGuard>} />
          <Route path="/dev/prompts" element={<AuthGuard><PromptInspector /></AuthGuard>} />
          <Route path="/dev/config" element={<AuthGuard><ConfigKeys /></AuthGuard>} />
          <Route path="/dev/simulation" element={<AuthGuard><Simulation /></AuthGuard>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}
