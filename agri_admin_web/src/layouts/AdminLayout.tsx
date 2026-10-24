import { useEffect, useMemo, useState } from 'react';
import { Layout, Menu, Button, Tooltip } from 'antd';
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
  UserOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { authStore } from '../stores/authStore';
import { layout, palette } from '../styles/theme';
import { useThemeMode } from '../theme/themeContext';
import ThemeToggle from '../components/ThemeToggle';
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
  '/assistant-settings': '助手设置',
  '/weather': '天气预报',
  '/users': '用户管理',
  '/memos': '提醒 / 备忘录',
  '/operations': '业务调试中心',
  '/dev/traces': '链路追踪',
  '/dev/tokens': 'Token 看板',
  '/dev/playground': 'Playground',
  '/dev/skills': 'Skill 注册表',
  '/dev/prompts': 'Prompt 管理',
  '/dev/config': '配置管理',
};

const brandLogoSrc = '/logo.png';
// 窄屏自动收为图标栏，把宽度让给内容区；用户仍可手动展开。
const SIDEBAR_COLLAPSE_QUERY = '(max-width: 1200px)';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const isFullScreen = location.pathname === '/dev/playground';
  const headerHeight = isFullScreen ? 52 : layout.headerHeight;
  const [sidebarState, setSidebarState] = useState(() => ({
    workspace: isFullScreen,
    collapsed: isFullScreen || window.matchMedia(SIDEBAR_COLLAPSE_QUERY).matches,
  }));
  // 进入工作区时采用紧凑导航；同一路由内保留用户手动展开的选择。
  if (sidebarState.workspace !== isFullScreen) {
    setSidebarState({ workspace: isFullScreen, collapsed: isFullScreen || window.matchMedia(SIDEBAR_COLLAPSE_QUERY).matches });
  }
  const { collapsed } = sidebarState;
  useEffect(() => {
    const query = window.matchMedia(SIDEBAR_COLLAPSE_QUERY);
    const sync = (event: MediaQueryListEvent) => setSidebarState({ workspace: isFullScreen, collapsed: event.matches || isFullScreen });
    query.addEventListener('change', sync);
    return () => query.removeEventListener('change', sync);
  }, [isFullScreen]);
  const { mode } = useThemeMode();
  const navigate = useNavigate();

  const currentTitle = pageTitles[location.pathname] || '田掌柜';
  const collapseLabel = collapsed ? '展开侧边栏' : '折叠侧边栏';
  const toggleSidebar = () => setSidebarState((current) => ({ ...current, collapsed: !current.collapsed }));
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
  const [menuState, setMenuState] = useState({
    activeParentKey,
    openKeys: activeParentKey ? [activeParentKey] : [],
  });
  // 仅跨业务分组导航时定位当前入口；同组内的手动收起必须保留。
  if (menuState.activeParentKey !== activeParentKey) {
    setMenuState({ activeParentKey, openKeys: activeParentKey ? [activeParentKey] : [] });
  }
  const displayedOpenKeys = collapsed ? [] : menuState.openKeys;
  const visibleMenuItems = collapsed ? collapsedMenuItems : menuItems;

  return (
    <Layout className={`app-shell${isFullScreen ? ' app-shell--playground' : ''}`} style={{ height: '100dvh', background: 'transparent' }}>
      <Sider
        width={232}
        collapsedWidth={68}
        collapsed={collapsed}
        className={`app-sider${collapsed ? ' app-sider--collapsed' : ''}`}
        style={{ overflow: 'hidden' }}
      >
        <div
          className="app-sidebar-brand"
          style={{
            // 与全局 header 同高，避免左侧品牌区与右侧顶栏出现横线错位。
            height: headerHeight,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'space-between',
            padding: collapsed ? 0 : '0 12px 0 16px',

            gap: 10,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
            <div
              className="app-brand-mark"
              style={{
                width: 32,
                height: 32,
                borderRadius: 10,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: 3,
                flexShrink: 0,
              }}
            >
              <img
                src={brandLogoSrc}
                alt="田掌柜"
                style={{ width: '100%', height: '100%', borderRadius: 7, objectFit: 'contain', display: 'block' }}
              />
            </div>
            {!collapsed && (
              <div className="app-brand-copy">
                <div className="app-brand-name">田掌柜</div>
                <div className="app-brand-tagline">智能种植运营助手</div>
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

        <div className="surface-scroll app-sidebar-navigation">
          {collapsed ? (
            <nav className="app-sidebar-collapsed-nav" aria-label={`${activeGroup.label}导航`}>
              {collapsedMenuItems.map((item) => (
                <Tooltip key={item.key} title={item.label} placement="right">
                  <Button
                    type="text"
                    aria-label={item.label}
                    aria-current={selectedKey === item.key ? 'page' : undefined}
                    className="app-sidebar-collapsed-nav-item"
                    data-active={selectedKey === item.key}
                    icon={item.icon}
                    onClick={() => navigate(item.key)}
                  />
                </Tooltip>
              ))}
            </nav>
          ) : (
            <Menu
              className="app-sidebar-menu"
              theme={mode === 'dark' ? 'dark' : 'light'}
              mode="inline"
              selectedKeys={[selectedKey]}
              openKeys={displayedOpenKeys}
              items={visibleMenuItems}
              onOpenChange={(keys) => {
                // 手风琴导航减少长列表滚动，空数组表示用户主动收起全部。
                const newlyOpened = keys.find((key) => !menuState.openKeys.includes(key));
                setMenuState({ activeParentKey, openKeys: newlyOpened ? [newlyOpened] : keys });
              }}
              onClick={({ key }: { key: string }) => {
                if (key.startsWith('/')) navigate(key);
              }}
              style={{
                background: 'transparent',
                borderRight: 'none',
                padding: '4px 0 10px',
              }}
            />
          )}
        </div>

        <div className="app-sidebar-footer">
          {!collapsed && (
            <>
              <div className="app-sidebar-account">
                <span className="app-sidebar-account__avatar"><UserOutlined /></span>
                <div><strong>管理员</strong><span>工作台账户</span></div>
              </div>
              <Tooltip title="退出登录">
                <Button type="text" aria-label="退出登录" icon={<LogoutOutlined />} onClick={() => { authStore.clearToken(); navigate('/login'); }} />
              </Tooltip>
            </>
          )}
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

      <Layout style={{ background: 'transparent', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Header
          className="app-header"
          style={{
            height: headerHeight,
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexShrink: 0,
          }}
        >
          <span className="app-header__title-block">
            <HomeOutlined style={{ color: palette.textMuted, fontSize: 15 }} />
            <span className="app-header__title-copy">
              <span className="app-header__eyebrow">工作台 /</span>
              <span className="app-header__page-title">
                {currentTitle}

              </span>
            </span>
          </span>
          <span className="app-header__user">
            <ThemeToggle compact={isFullScreen} />
            {!isFullScreen && <span className="app-header__date">
              {new Date().toLocaleDateString('zh-CN')}
            </span>}
            {collapsed && <Button type="text" aria-label="退出登录" icon={<LogoutOutlined />} onClick={() => { authStore.clearToken(); navigate('/login'); }} />}
          </span>
        </Header>

        <Content
          className="app-content-scroll"
          style={{
            flex: 1,
            minHeight: 0,
            padding: isFullScreen ? 0 : 'var(--app-content-padding) var(--app-content-padding) 56px',
            background: 'transparent',
            overflow: isFullScreen ? 'hidden' : 'auto',
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
}
