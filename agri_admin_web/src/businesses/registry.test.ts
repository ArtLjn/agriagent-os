import { describe, expect, it } from 'vitest';

import { platformMenuGroups } from '../layouts/adminMenu';
import {
  PLATFORM_ROUTE_PREFIXES,
  businessViews,
  matchesRoutePrefix,
  menuGroupsFor,
} from './registry';

const farm = businessViews[0];
const companion = businessViews[1];

describe('business registry', () => {
  it('农场业务分组包含全部农事入口且不重复', () => {
    const keys = farm.groups.flatMap((group) => group.children.map((item) => item.key));

    expect(keys).toEqual([
      '/dashboard',
      '/crops',
      '/crops/system',
      '/cycles',
      '/logs',
      '/costs',
      '/weather',
      '/memos',
      '/operations',
      '/agent',
    ]);
    expect(new Set(keys).size).toBe(keys.length);
    expect(farm.homePath).toBe('/dashboard');
  });

  it('陪伴关怀业务包含陪伴空间和独立对话入口', () => {
    const keys = companion.groups.flatMap((group) => group.children.map((item) => item.key));

    expect(keys).toEqual(['/companion', '/companion/chat']);
    expect(companion.homePath).toBe('/companion');
  });

  it('业务之间的路由前缀不重叠', () => {
    expect(
      farm.routePrefixes.some(
        (prefix) => prefix === '/companion' || '/companion'.startsWith(`${prefix}/`),
      ),
    ).toBe(false);
    expect(companion.routePrefixes).toEqual(['/companion']);
  });

  it('平台分组固定包含业务中心与用户管理', () => {
    const platformKeys = platformMenuGroups.flatMap(
      (group) => group.children.map((item) => item.key),
    );

    expect(platformKeys).toContain('/businesses');
    expect(platformKeys).toContain('/users');
    expect(platformKeys).toContain('/assistant-settings');
  });

  it('业务路由与平台路由不重叠', () => {
    for (const platformPrefix of PLATFORM_ROUTE_PREFIXES) {
      expect(
        farm.routePrefixes.some(
          (prefix) => prefix === platformPrefix || prefix.startsWith(`${platformPrefix}/`),
        ),
      ).toBe(false);
    }
  });

  it('按路径段边界匹配业务路由', () => {
    expect(matchesRoutePrefix('/crops/system', ['/crops'])).toBe(true);
    expect(matchesRoutePrefix('/cycles/42', ['/cycles'])).toBe(true);
    expect(matchesRoutePrefix('/cropshop', ['/crops'])).toBe(false);
  });

  it('组合菜单时业务分组在前、平台分组在后', () => {
    const groups = menuGroupsFor(farm);

    expect(groups[0].label).toBe('农场业务');
    expect(groups.at(-1)?.label).toBe(platformMenuGroups.at(-1)?.label);
  });
});
