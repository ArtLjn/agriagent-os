import { describe, expect, it } from 'vitest';

import { parseApiError } from './client';

describe('统一 API 错误解析', () => {
  it.each([
    [401, { detail: { code: 'token_expired', message: '令牌已过期' } }, 'token_expired', '令牌已过期'],
    [403, { detail: { code: 'permission_denied', message: '无权访问' } }, 'permission_denied', '无权访问'],
    [409, { detail: { code: 'duplicate', message: '记录已存在' } }, 'duplicate', '记录已存在'],
    [422, { detail: { code: 'validation_error', message: '请求参数校验失败' } }, 'validation_error', '请求参数校验失败'],
    [503, { detail: { code: 'dependency_unavailable', message: '服务暂不可用' } }, 'dependency_unavailable', '服务暂不可用'],
  ])('%s 保留 detail.code 和 detail.message', (_status, payload, code, message) => {
    expect(parseApiError(payload)).toEqual({ code, message, fields: [] });
  });

  it('兼容历史字符串 detail', () => {
    expect(parseApiError({ detail: '手机号或密码错误' })).toEqual({
      message: '手机号或密码错误',
      fields: [],
    });
  });

  it('兼容统一 detail.meta.errors 和旧 errors 字段', () => {
    expect(parseApiError({
      detail: {
        code: 'validation_error',
        message: '请求参数校验失败',
        meta: { errors: [{ loc: ['body', 'name'], msg: '字段必填' }] },
      },
    }).fields).toEqual(['body.name: 字段必填']);
    expect(parseApiError({
      detail: '参数错误',
      errors: [{ field: 'name', message: '字段必填' }],
    }).fields).toEqual(['name: 字段必填']);
  });
});
