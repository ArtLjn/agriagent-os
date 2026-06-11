import { useMemo, useState } from 'react';
import { Layout, Menu, Button, Tooltip, Tag } from 'antd';
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  BranchesOutlined,
  BarChartOutlined,
  MessageOutlined,
  AppstoreOutlined,
  FileSearchOutlined,
  SettingOutlined,
  TeamOutlined,
  LogoutOutlined,
  ExperimentOutlined,
  CloudOutlined,
  DollarOutlined,
  FieldTimeOutlined,
  FormOutlined,
  HomeOutlined,
  ReadOutlined,
  RobotOutlined,
  ToolOutlined,
  ControlOutlined,
  DatabaseOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { authStore } from '../stores/authStore';
import { layout, palette } from '../styles/theme';

const { Sider, Content, Header } = Layout;

const menuGroups = [
  {
    key: 'user-ops',
    icon: <TeamOutlined />,
    label: '业务运营',
    children: [
      { key: '/dashboard', icon: <HomeOutlined />, label: '仪表盘' },
      { key: '/users', icon: <TeamOutlined />, label: '用户管理' },
      { key: '/crops', icon: <ReadOutlined />, label: '作物模板' },
      { key: '/cycles', icon: <FieldTimeOutlined />, label: '种植周期' },
      { key: '/logs', icon: <FormOutlined />, label: '农事日志' },
      { key: '/costs', icon: <DollarOutlined />, label: '成本记账' },
      { key: '/weather', icon: <CloudOutlined />, label: '天气预报' },
    ],
  },
  {
    key: 'assistant-workbench',
    icon: <ControlOutlined />,
    label: '业务调试',
    children: [
      { key: '/operations', icon: <ControlOutlined />, label: '业务调试中心' },
      { key: '/agent', icon: <RobotOutlined />, label: 'AI 助手' },
    ],
  },
  {
    key: 'agent-platform',
    icon: <ToolOutlined />,
    label: 'Agent 平台',
    children: [
      { key: '/dev/traces', icon: <BranchesOutlined />, label: '链路追踪' },
      { key: '/dev/tokens', icon: <BarChartOutlined />, label: 'Token 看板' },
      { key: '/dev/playground', icon: <MessageOutlined />, label: 'Playground' },
      { key: '/dev/data-flywheel', icon: <DatabaseOutlined />, label: '数据飞轮' },
      { key: '/dev/skills', icon: <AppstoreOutlined />, label: 'Skill 注册表' },
      { key: '/dev/prompts', icon: <FileSearchOutlined />, label: 'Prompt 检查器' },
      { key: '/dev/simulation', icon: <ExperimentOutlined />, label: '仿真测试' },
      { key: '/dev/config', icon: <SettingOutlined />, label: '配置管理' },
    ],
  },
];

const menuItems = [
  ...menuGroups.map((group) => ({
    key: group.key,
    icon: group.icon,
    label: group.label,
    children: group.children,
  })),
];

const pageTitles: Record<string, string> = {
  '/dashboard': '仪表盘',
  '/crops': '作物模板',
  '/cycles': '种植周期',
  '/logs': '农事日志',
  '/costs': '成本记账',
  '/agent': 'AI 助手',
  '/weather': '天气预报',
  '/users': '用户管理',
  '/operations': '业务调试中心',
  '/dev/traces': '链路追踪',
  '/dev/tokens': 'Token 看板',
  '/dev/playground': 'Playground',
  '/dev/data-flywheel': '数据飞轮',
  '/dev/skills': 'Skill 注册表',
  '/dev/prompts': 'Prompt 检查器',
  '/dev/simulation': '仿真测试',
  '/dev/config': '配置管理',
};

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [openKeys, setOpenKeys] = useState<string[]>(['user-ops', 'assistant-workbench', 'agent-platform']);
  const navigate = useNavigate();
  const location = useLocation();

  const currentTitle = pageTitles[location.pathname] || 'Farm Manager';
  const selectedKey = useMemo(() => {
    if (location.pathname.startsWith('/cycles/')) return '/cycles';
    return location.pathname;
  }, [location.pathname]);
  const activeParentKey = useMemo(() => (
    menuGroups.find((group) => group.children.some((item) => item.key === selectedKey))?.key
  ), [selectedKey]);
  const displayedOpenKeys = collapsed
    ? []
    : activeParentKey && !openKeys.includes(activeParentKey)
      ? [...openKeys, activeParentKey]
      : openKeys;

  return (
    <Layout className="app-shell" style={{ height: '100vh', background: palette.bg }}>
      <Sider
        width={232}
        collapsedWidth={68}
        collapsed={collapsed}
        style={{
          background: palette.bgElevated,
          borderRight: `1px solid ${palette.border}`,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: layout.headerHeight,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            padding: collapsed ? 0 : '0 20px',
            borderBottom: `1px solid ${palette.border}`,
            gap: 10,
          }}
        >
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 8,
              background: `linear-gradient(135deg, ${palette.accent} 0%, ${palette.success} 100%)`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <span style={{ color: '#fff', fontSize: 14, fontWeight: 'bold' }}>F</span>
          </div>
          {!collapsed && (
            <div style={{ minWidth: 0 }}>
              <div style={{ color: palette.text, fontSize: 15, fontWeight: 700, whiteSpace: 'nowrap' }}>
                Farm Manager
              </div>
              <div style={{ color: palette.textMuted, fontSize: 11, marginTop: 2 }}>
                智能种植运营台
              </div>
            </div>
          )}
        </div>

        <div className="surface-scroll" style={{ height: `calc(100vh - ${layout.headerHeight + 48}px)`, overflow: 'auto', paddingTop: 6 }}>
          <Menu
            className="app-sidebar-menu"
            theme="dark"
            mode="inline"
            selectedKeys={[selectedKey]}
            openKeys={displayedOpenKeys}
            items={menuItems}
            onOpenChange={(keys) => setOpenKeys(keys)}
            onClick={({ key }: { key: string }) => {
              if (key.startsWith('/')) navigate(key);
            }}
            style={{
              background: 'transparent',
              borderRight: 'none',
              padding: '4px 0 10px',
            }}
          />
        </div>

        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            height: 48,
            borderTop: `1px solid ${palette.border}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-end',
            padding: collapsed ? 0 : '0 16px',
            background: palette.bgElevated,
          }}
        >
          <Tooltip title={collapsed ? '展开' : '收起'} placement="right">
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              style={{ color: palette.textMuted }}
            />
          </Tooltip>
        </div>
      </Sider>

      <Layout style={{ background: palette.bg, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Header
          style={{
            background: palette.bgElevated,
            height: layout.headerHeight,
            padding: '0 24px',
            borderBottom: `1px solid ${palette.border}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexShrink: 0,
          }}
        >
          <span style={{ fontSize: 15, fontWeight: 600, color: palette.text, display: 'flex', alignItems: 'center', gap: 10 }}>
            <HomeOutlined style={{ color: palette.textMuted }} />
            {currentTitle}
            <Tag color="blue" style={{ marginLeft: 2 }}>admin</Tag>
          </span>
          <span style={{ fontSize: 12, color: palette.textMuted }}>
            {new Date().toLocaleDateString('zh-CN')}
            <Button
              type="text"
              icon={<LogoutOutlined />}
              onClick={() => { authStore.clearToken(); navigate('/login'); }}
              style={{ color: palette.textMuted, marginLeft: 16, fontSize: 12 }}
            >
              退出登录
            </Button>
          </span>
        </Header>

        <Content
          className="app-content-scroll"
          style={{
            flex: 1,
            minHeight: 0,
            padding: '20px 24px 56px',
            background: palette.bg,
            overflow: 'auto',
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
}
