import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AdminLayout from './layouts/AdminLayout';
import Dashboard from './pages/Dashboard';
import Crops from './pages/Crops';
import Cycles from './pages/Cycles';
import CycleDetail from './pages/Cycles/Detail';
import Logs from './pages/Logs';
import Costs from './pages/Costs';
import Agent from './pages/Agent';
import Weather from './pages/Weather';
import ApiTester from './pages/ApiTester';

export default function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <BrowserRouter>
        <AdminLayout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/crops" element={<Crops />} />
            <Route path="/cycles" element={<Cycles />} />
            <Route path="/cycles/:id" element={<CycleDetail />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/costs" element={<Costs />} />
            <Route path="/agent" element={<Agent />} />
            <Route path="/weather" element={<Weather />} />
            <Route path="/api-tester" element={<ApiTester />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AdminLayout>
      </BrowserRouter>
    </ConfigProvider>
  );
}
