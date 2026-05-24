import { useState } from 'react';
import { Layout, Menu } from 'antd';
import {
  DashboardOutlined,
  EnvironmentOutlined,
  SwapOutlined,
  FileTextOutlined,
  DollarOutlined,
  RobotOutlined,
  CloudOutlined,
  ApiOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';

const { Sider, Content, Header } = Layout;

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/crops', icon: <EnvironmentOutlined />, label: '作物管理' },
  { key: '/cycles', icon: <SwapOutlined />, label: '茬口管理' },
  { key: '/logs', icon: <FileTextOutlined />, label: '农事日志' },
  { key: '/costs', icon: <DollarOutlined />, label: '成本记账' },
  { key: '/agent', icon: <RobotOutlined />, label: 'AI 助手' },
  { key: '/weather', icon: <CloudOutlined />, label: '天气预报' },
  { key: '/api-tester', icon: <ApiOutlined />, label: 'API Tester' },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
        <div style={{ height: 32, margin: 16, color: '#fff', textAlign: 'center', fontSize: 18, fontWeight: 'bold' }}>
          {collapsed ? 'FM' : 'Farm Manager'}
        </div>
        <Menu
          theme="dark"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }: { key: string }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 24px', fontSize: 20, fontWeight: 'bold' }}>
          Farm Manager 管理端
        </Header>
        <Content style={{ margin: 24 }}>{children}</Content>
      </Layout>
    </Layout>
  );
}
