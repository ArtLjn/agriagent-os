import { describe, expect, it } from 'vitest';

import { chooseDefaultUserId } from './currentUser';

describe('chooseDefaultUserId', () => {
  it('当前登录用户存在于列表时默认选中当前用户', () => {
    expect(chooseDefaultUserId(
      { id: 'u-admin' },
      [
        { id: 'anonymous' },
        { id: 'u-admin' },
      ],
    )).toBe('u-admin');
  });

  it('当前用户不在列表时不回落到匿名用户', () => {
    expect(chooseDefaultUserId(
      { id: 'u-admin' },
      [{ id: 'anonymous' }],
    )).toBeNull();
  });
});
