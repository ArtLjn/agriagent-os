export type AdminMenuIcon =
  | 'agent'
  | 'appstore'
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
  | 'heart'
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
  disabled?: boolean;
}

export interface AdminMenuGroup {
  key: string;
  icon: AdminMenuIcon;
  label: string;
  disabled?: boolean;
  children: AdminMenuItem[];
}

export const platformMenuGroups: AdminMenuGroup[] = [
  {
    key: 'platform:manage',
    icon: 'appstore',
    label: '平台管理',
    children: [
      { key: '/businesses', icon: 'appstore', label: '业务中心' },
      { key: '/users', icon: 'team', label: '用户管理' },
      { key: '/assistant-settings', icon: 'setting', label: '助手设置' },
    ],
  },
  {
    key: 'platform:agent',
    icon: 'tool',
    label: 'Agent 开发',
    children: [
      { key: '/dev/playground', icon: 'message', label: 'Playground' },
      { key: '/dev/skills', icon: 'agent', label: 'Skill 注册表' },
      { key: '/dev/prompts', icon: 'fileSearch', label: 'Prompt 管理' },
    ],
  },
  {
    key: 'platform:observability',
    icon: 'chart',
    label: '运行监控',
    children: [
      { key: '/dev/traces', icon: 'branches', label: '链路追踪' },
      { key: '/dev/tokens', icon: 'chart', label: 'Token 看板' },
    ],
  },
  {
    key: 'platform:system',
    icon: 'setting',
    label: '系统管理',
    children: [
      { key: '/dev/config', icon: 'setting', label: '配置管理' },
    ],
  },
];
