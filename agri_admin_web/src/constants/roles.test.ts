import { describe, expect, it } from 'vitest';

import {
  getSsePresentationProfile,
  roleLabel,
  USER_ROLES,
} from './roles';

describe('user roles', () => {
  it('keeps dev on the same SSE user view as user', () => {
    expect(getSsePresentationProfile(USER_ROLES.USER)).toBe('user');
    expect(getSsePresentationProfile(USER_ROLES.DEV)).toBe('user');
    expect(getSsePresentationProfile(USER_ROLES.ADMIN)).toBe('admin_debug');
  });

  it('exposes explicit labels for all supported roles', () => {
    expect(roleLabel(USER_ROLES.ADMIN)).toBe('管理员');
    expect(roleLabel(USER_ROLES.USER)).toBe('普通用户');
    expect(roleLabel(USER_ROLES.DEV)).toBe('调试用户');
  });
});
