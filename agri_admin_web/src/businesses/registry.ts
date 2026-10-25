import type { AdminMenuGroup, AdminMenuIcon } from '../layouts/adminMenu';
import { platformMenuGroups } from '../layouts/adminMenu';

export interface BusinessView {
  /** 对应后端 plugin.yaml 的 name。 */
  name: string;
  displayName: string;
  description: string;
  icon: AdminMenuIcon;
  homePath: string;
  /** 显式声明该业务的页面归属，按路径段边界匹配。 */
  routePrefixes: string[];
  groups: AdminMenuGroup[];
}

export const PLATFORM_ROUTE_PREFIXES = [
  '/businesses',
  '/users',
  '/assistant-settings',
  '/dev',
];

export const businessViews: BusinessView[] = [
  {
    name: 'farm',
    displayName: '农场业务',
    description: '作物模板、种植周期、农事日志与成本经营的一体化管理。',
    icon: 'experiment',
    homePath: '/dashboard',
    routePrefixes: [
      '/dashboard',
      '/crops',
      '/cycles',
      '/logs',
      '/costs',
      '/weather',
      '/memos',
      '/operations',
      '/agent',
    ],
    groups: [
      {
        key: 'farm:operations',
        icon: 'experiment',
        label: '农场业务',
        children: [
          { key: '/dashboard', icon: 'home', label: '仪表盘' },
          { key: '/crops', icon: 'read', label: '作物模板' },
          { key: '/crops/system', icon: 'read', label: '系统模板' },
          { key: '/cycles', icon: 'fieldTime', label: '种植周期' },
          { key: '/logs', icon: 'form', label: '农事日志' },
          { key: '/costs', icon: 'dollar', label: '成本记账' },
          { key: '/weather', icon: 'cloud', label: '天气预报' },
          { key: '/memos', icon: 'form', label: '提醒 / 备忘录' },
          { key: '/operations', icon: 'control', label: '业务调试中心' },
          { key: '/agent', icon: 'agent', label: 'AI 助手' },
        ],
      },
    ],
  },
  {
    name: 'companion',
    displayName: '陪伴关怀',
    description: '日常陪伴、情绪关怀和轻量关怀建议。',
    icon: 'heart',
    homePath: '/companion',
    routePrefixes: ['/companion'],
    groups: [
      {
        key: 'companion:care',
        icon: 'heart',
        label: '陪伴关怀',
        children: [
          { key: '/companion', icon: 'heart', label: '陪伴空间' },
          { key: '/companion/chat', icon: 'agent', label: '陪伴对话' },
        ],
      },
    ],
  },
];

export function menuGroupsFor(view: BusinessView | null): AdminMenuGroup[] {
  return view ? [...view.groups, ...platformMenuGroups] : platformMenuGroups;
}

export function matchesRoutePrefix(pathname: string, prefixes: string[]): boolean {
  return prefixes.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}
