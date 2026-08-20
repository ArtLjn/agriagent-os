export type AdminMenuIcon =
  | 'agent'
  | 'branches'
  | 'chart'
  | 'cloud'
  | 'control'
  | 'database'
  | 'dollar'
  | 'experiment'
  | 'fieldTime'
  | 'fileSearch'
  | 'form'
  | 'home'
  | 'message'
  | 'read'
  | 'setting'
  | 'team'
  | 'tool';

export interface AdminMenuItem {
  key: string;
  icon: AdminMenuIcon;
  label: string;
}

export interface AdminMenuGroup {
  key: string;
  icon: AdminMenuIcon;
  label: string;
  children: AdminMenuItem[];
}

export const menuGroups: AdminMenuGroup[] = [
  {
    key: 'user-ops',
    icon: 'team',
    label: '业务运营',
    children: [
      { key: '/dashboard', icon: 'home', label: '仪表盘' },
      { key: '/users', icon: 'team', label: '用户管理' },
      { key: '/crops/system', icon: 'read', label: '系统模板' },
    ],
  },
  {
    key: 'assistant-workbench',
    icon: 'control',
    label: '业务调试',
    children: [
      { key: '/operations', icon: 'control', label: '业务调试中心' },
      { key: '/crops', icon: 'read', label: '作物模板' },
      { key: '/cycles', icon: 'fieldTime', label: '种植周期' },
      { key: '/logs', icon: 'form', label: '农事日志' },
      { key: '/costs', icon: 'dollar', label: '成本记账' },
      { key: '/weather', icon: 'cloud', label: '天气预报' },
      { key: '/agent', icon: 'agent', label: 'AI 助手' },
    ],
  },
  {
    key: 'agent-platform',
    icon: 'tool',
    label: 'Agent 平台',
    children: [
      { key: '/dev/traces', icon: 'branches', label: '链路追踪' },
      { key: '/dev/tokens', icon: 'chart', label: 'Token 看板' },
      { key: '/dev/playground', icon: 'message', label: 'Playground' },
      { key: '/dev/data-flywheel', icon: 'database', label: '数据飞轮' },
      { key: '/dev/skills', icon: 'agent', label: 'Skill 注册表' },
      { key: '/dev/prompts', icon: 'fileSearch', label: 'Prompt 检查器' },
      { key: '/dev/simulation', icon: 'experiment', label: '仿真测试' },
      { key: '/dev/config', icon: 'setting', label: '配置管理' },
    ],
  },
];
