export const USER_ROLES = {
  ADMIN: 'admin',
  USER: 'user',
  DEV: 'dev',
} as const;

export type UserRole = (typeof USER_ROLES)[keyof typeof USER_ROLES];

export const USER_ROLE_OPTIONS: Array<{ value: UserRole; label: string; description: string }> = [
  { value: USER_ROLES.USER, label: '普通用户', description: '正常业务使用' },
  { value: USER_ROLES.DEV, label: '调试用户', description: '测试调试账号，与普通用户权限一致' },
  { value: USER_ROLES.ADMIN, label: '管理员', description: '管理端与 SSE 调试权限' },
];

export function isAdminRole(role: string | null | undefined): boolean {
  return role === USER_ROLES.ADMIN;
}

export function roleLabel(role: string | null | undefined): string {
  return USER_ROLE_OPTIONS.find((item) => item.value === role)?.label ?? role ?? '未知角色';
}

export function getSsePresentationProfile(role: string | null | undefined): 'user' | 'admin_debug' {
  return isAdminRole(role) ? 'admin_debug' : 'user';
}
