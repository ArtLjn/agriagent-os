import { useState } from 'react';
import { Layout, Menu, Button, Tooltip } from 'antd';
import {
  DashboardOutlined,
  EnvironmentOutlined,
  SwapOutlined,
  FileTextOutlined,
  DollarOutlined,
  RobotOutlined,
  CloudOutlined,
  ApiOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  BranchesOutlined,
  BarChartOutlined,
  MessageOutlined,
  AppstoreOutlined,
  FileSearchOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';

const { Sider, Content, Header } = Layout;

const BG_PRIMARY = '#0d1117';
const BG_SECONDARY = '#161b22';
const BG_CARD = '#21262d';
const BORDER = '#30363d';
const TEXT_PRIMARY = '#c9d1d9';
const TEXT_SECONDARY = '#8b949e';
const ACCENT = '#58a6ff';

const menuItems = [
  {
    type: 'group',
    label: '业务管理',
    children: [
      { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
      { key: '/crops', icon: <EnvironmentOutlined />, label: '作物管理' },
      { key: '/cycles', icon: <SwapOutlined />, label: '茬口管理' },
      { key: '/logs', icon: <FileTextOutlined />, label: '农事日志' },
      { key: '/costs', icon: <DollarOutlined />, label: '成本记账' },
      { key: '/agent', icon: <RobotOutlined />, label: 'AI 助手' },
      { key: '/weather', icon: <CloudOutlined />, label: '天气预报' },
      { key: '/api-tester', icon: <ApiOutlined />, label: 'API Tester' },
    ],
  },
  {
    type: 'group',
    label: '开发调试',
    children: [
      { key: '/dev/traces', icon: <BranchesOutlined />, label: '链路追踪' },
      { key: '/dev/tokens', icon: <BarChartOutlined />, label: 'Token 看板' },
      { key: '/dev/playground', icon: <MessageOutlined />, label: 'Playground' },
      { key: '/dev/skills', icon: <AppstoreOutlined />, label: 'Skill 注册表' },
      { key: '/dev/prompts', icon: <FileSearchOutlined />, label: 'Prompt 检查器' },
      { key: '/dev/config', icon: <SettingOutlined />, label: '配置管理' },
    ],
  },
];

const pageTitles: Record<string, string> = {
  '/': '仪表盘',
  '/crops': '作物管理',
  '/cycles': '茬口管理',
  '/logs': '农事日志',
  '/costs': '成本记账',
  '/agent': 'AI 助手',
  '/weather': '天气预报',
  '/api-tester': 'API Tester',
  '/dev/traces': '链路追踪',
  '/dev/tokens': 'Token 看板',
  '/dev/playground': 'Playground',
  '/dev/skills': 'Skill 注册表',
  '/dev/prompts': 'Prompt 检查器',
  '/dev/config': '配置管理',
};

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const currentTitle = pageTitles[location.pathname] || 'Farm Manager';

  return (
    <Layout style={{ minHeight: '100vh', background: BG_PRIMARY }}>
      <Sider
        width={200}
        collapsedWidth={64}
        collapsed={collapsed}
        style={{
          background: BG_SECONDARY,
          borderRight: `1px solid ${BORDER}`,
          overflow: 'hidden',
        }}
      >
        {/* Logo */}
        <div
          style={{
            height: 56,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            padding: collapsed ? 0 : '0 20px',
            borderBottom: `1px solid ${BORDER}`,
            gap: 10,
          }}
        >
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              background: 'linear-gradient(135deg, #58a6ff 0%, #238636 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <span style={{ color: '#fff', fontSize: 14, fontWeight: 'bold' }}>F</span>
          </div>
          {!collapsed && (
            <span style={{ color: ACCENT, fontSize: 16, fontWeight: 700, letterSpacing: 0.5, whiteSpace: 'nowrap' }}>
              Farm Manager
            </span>
          )}
        </div>

        {/* Menu */}
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }: { key: string }) => navigate(key)}
          style={{
            background: 'transparent',
            borderRight: 'none',
            padding: '8px 0',
          }}
        />

        {/* Collapse button at bottom */}
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            height: 48,
            borderTop: `1px solid ${BORDER}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-end',
            padding: collapsed ? 0 : '0 16px',
            background: BG_SECONDARY,
          }}
        >
          <Tooltip title={collapsed ? '展开' : '收起'} placement="right">
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              style={{ color: TEXT_SECONDARY }}
            />
          </Tooltip>
        </div>
      </Sider>

      <Layout style={{ background: BG_PRIMARY }}>
        {/* Header */}
        <Header
          style={{
            background: BG_SECONDARY,
            height: 56,
            padding: '0 24px',
            borderBottom: `1px solid ${BORDER}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ fontSize: 16, fontWeight: 600, color: TEXT_PRIMARY }}>
            {currentTitle}
          </span>
          <span style={{ fontSize: 12, color: TEXT_SECONDARY }}>
            {new Date().toLocaleDateString('zh-CN')}
          </span>
        </Header>

        {/* Content */}
        <Content
          style={{
            margin: 20,
            padding: 20,
            background: BG_CARD,
            borderRadius: 12,
            border: `1px solid ${BORDER}`,
            overflow: 'auto',
            minHeight: 'calc(100vh - 96px)',
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
}
