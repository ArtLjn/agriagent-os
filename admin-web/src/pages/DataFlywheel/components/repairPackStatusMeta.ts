import type { RepairPackStatus } from '../../../api/dataFlywheel';

export interface RepairPackStatusMeta {
  label: string;
  color: string;
}

export const REPAIR_PACK_STATUS_META: Record<RepairPackStatus, RepairPackStatusMeta> = {
  draft: { label: '草稿', color: 'default' },
  exported: { label: '已导出', color: 'blue' },
  export_failed: { label: '导出失败', color: 'red' },
  verification_failed: { label: '验证失败', color: 'orange' },
  resolved: { label: '已修复', color: 'green' },
  discarded: { label: '已废弃', color: 'default' },
};

export const REPAIR_PACK_STATUS_OPTIONS: { label: string; value: RepairPackStatus }[] = [
  { label: '已导出', value: 'exported' },
  { label: '导出失败', value: 'export_failed' },
  { label: '验证失败', value: 'verification_failed' },
  { label: '已修复', value: 'resolved' },
  { label: '已废弃', value: 'discarded' },
];

export function repairPackStatusMeta(status: string): RepairPackStatusMeta {
  if (status in REPAIR_PACK_STATUS_META) {
    return REPAIR_PACK_STATUS_META[status as RepairPackStatus];
  }
  return { label: status || '未知', color: 'default' };
}
