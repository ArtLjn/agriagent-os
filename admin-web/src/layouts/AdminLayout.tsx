import { useMemo, useState } from 'react';
import { Layout, Menu, Button, Tooltip, Tag } from 'antd';
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  BranchesOutlined,
  BarChartOutlined,
  MessageOutlined,
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
import { menuGroups, type AdminMenuIcon } from './adminMenu';

const { Sider, Content, Header } = Layout;

const iconByName: Record<AdminMenuIcon, React.ReactNode> = {
  agent: <RobotOutlined />,
  branches: <BranchesOutlined />,
  chart: <BarChartOutlined />,
  cloud: <CloudOutlined />,
  control: <ControlOutlined />,
  database: <DatabaseOutlined />,
  dollar: <DollarOutlined />,
  experiment: <ExperimentOutlined />,
  fieldTime: <FieldTimeOutlined />,
  fileSearch: <FileSearchOutlined />,
  form: <FormOutlined />,
  home: <HomeOutlined />,
  message: <MessageOutlined />,
  read: <ReadOutlined />,
  setting: <SettingOutlined />,
  team: <TeamOutlined />,
  tool: <ToolOutlined />,
};

const menuItems = [
  ...menuGroups.map((group) => ({
    key: group.key,
    icon: iconByName[group.icon],
    label: group.label,
    children: group.children.map((item) => ({
      ...item,
      icon: iconByName[item.icon],
    })),
  })),
];

const pageTitles: Record<string, string> = {
  '/dashboard': '仪表盘',
  '/crops': '作物模板',
  '/crops/system': '系统模板',
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

const brandLogoSrc = '/logo.png';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [openKeys, setOpenKeys] = useState<string[]>(['user-ops', 'assistant-workbench', 'agent-platform']);
  const navigate = useNavigate();
  const location = useLocation();

  const currentTitle = pageTitles[location.pathname] || '田掌柜';
  const collapseLabel = collapsed ? '展开侧边栏' : '折叠侧边栏';
  const toggleSidebar = () => setCollapsed((current) => !current);
  const selectedKey = useMemo(() => {
    if (location.pathname.startsWith('/cycles/')) return '/cycles';
    if (location.pathname.startsWith('/crops/system')) return '/crops/system';
    return location.pathname;
  }, [location.pathname]);
  const activeParentKey = useMemo(() => (
    menuGroups.find((group) => group.children.some((item) => item.key === selectedKey))?.key
  ), [selectedKey]);
  const activeGroup = useMemo(() => (
    menuGroups.find((group) => group.key === activeParentKey) ?? menuGroups[0]
  ), [activeParentKey]);
  const collapsedMenuItems = useMemo(() => (
    activeGroup.children.map((item) => ({
      ...item,
      icon: iconByName[item.icon],
    }))
  ), [activeGroup]);
  const displayedOpenKeys = collapsed
    ? []
    : activeParentKey && !openKeys.includes(activeParentKey)
      ? [...openKeys, activeParentKey]
      : openKeys;
  const visibleMenuItems = collapsed ? collapsedMenuItems : menuItems;

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
            justifyContent: collapsed ? 'center' : 'space-between',
            padding: collapsed ? 0 : '0 12px 0 20px',
            borderBottom: `1px solid ${palette.border}`,
            gap: 10,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: 10,
                background: '#fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: 3,
                flexShrink: 0,
                boxShadow: '0 10px 24px rgba(0, 0, 0, 0.18)',
              }}
            >
              <img
                src={brandLogoSrc}
                alt="田掌柜"
                style={{ width: '100%', height: '100%', borderRadius: 7, objectFit: 'contain', display: 'block' }}
              />
            </div>
            {!collapsed && (
              <div style={{ minWidth: 0 }}>
                <div style={{ color: palette.text, fontSize: 15, fontWeight: 700, whiteSpace: 'nowrap' }}>
                  田掌柜
                </div>
                <div style={{ color: palette.textMuted, fontSize: 11, marginTop: 2 }}>
                  智能种植运营助手
                </div>
              </div>
            )}
          </div>
          {!collapsed && (
            <Tooltip title={collapseLabel} placement="right">
              <Button
                type="text"
                aria-label={collapseLabel}
                icon={<MenuFoldOutlined />}
                onClick={toggleSidebar}
                style={{
                  color: palette.textMuted,
                  flexShrink: 0,
                  width: 30,
                  height: 30,
                }}
              />
            </Tooltip>
          )}
        </div>

        <div className="surface-scroll" style={{ height: `calc(100vh - ${layout.headerHeight + 48}px)`, overflow: 'auto', paddingTop: 6 }}>
          <Menu
            className="app-sidebar-menu"
            theme="dark"
            mode="inline"
            selectedKeys={[selectedKey]}
            openKeys={collapsed ? undefined : displayedOpenKeys}
            items={visibleMenuItems}
            onOpenChange={collapsed ? undefined : (keys) => setOpenKeys(keys)}
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
          <Tooltip title={collapseLabel} placement="right">
            <Button
              type="text"
              aria-label={collapsed ? collapseLabel : '底部折叠侧边栏'}
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={toggleSidebar}
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
