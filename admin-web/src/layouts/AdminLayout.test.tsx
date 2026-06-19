import { describe, expect, it } from 'vitest';

import { menuGroups } from './adminMenu';

function groupByLabel(label: string) {
  const group = menuGroups.find((item) => item.label === label);
  if (!group) {
    throw new Error(`未找到菜单分组：${label}`);
  }
  return group.children.map((item) => item.key);
}

describe('AdminLayout 菜单信息架构', () => {
  it('业务运营只放平台运营资产入口', () => {
    expect(groupByLabel('业务运营')).toEqual([
      '/dashboard',
      '/users',
      '/crops/system',
    ]);
  });

  it('业务调试归纳管理员个人 app 账号的业务数据视图', () => {
    expect(groupByLabel('业务调试')).toEqual([
      '/operations',
      '/crops',
      '/cycles',
      '/logs',
      '/costs',
      '/weather',
      '/agent',
    ]);
  });
});
