import type {
  DetailLevel,
  DisplayFormat,
  ExecutionDetailLevel,
  MemoryKind,
  MemoryScope,
  MemorySourceType,
  MemoryStatus,
  ReplyStyle,
} from "../../api/personalization";

export interface ValueOption<T extends string> {
  value: T;
  label: string;
  description: string;
}

export const REPLY_STYLE_OPTIONS: ValueOption<ReplyStyle>[] = [
  { value: "default", label: "默认", description: "跟随产品默认表达" },
  { value: "friendly", label: "亲和易懂", description: "少用术语，像农友聊天" },
  { value: "professional", label: "专业严谨", description: "结论明确，依据完整" },
  { value: "efficient", label: "高效务实", description: "直接给结果和下一步" },
];

export const DETAIL_LEVEL_OPTIONS: ValueOption<DetailLevel>[] = [
  { value: "concise", label: "简洁", description: "先给结论" },
  { value: "balanced", label: "适中", description: "结论加关键依据" },
  { value: "detailed", label: "详细", description: "补充过程和示例" },
];

export const DISPLAY_FORMAT_OPTIONS: ValueOption<DisplayFormat>[] = [
  { value: "auto", label: "自动", description: "按内容选择" },
  { value: "table", label: "优先表格", description: "适合对比数据" },
  { value: "list", label: "优先列表", description: "适合步骤与清单" },
];

export const EXECUTION_DETAIL_OPTIONS: ValueOption<ExecutionDetailLevel>[] = [
  { value: "concise", label: "精简", description: "只展示关键步骤" },
  { value: "detailed", label: "详细", description: "展示完整执行过程" },
];

export const MEMORY_SCOPE_META: Record<MemoryScope, { label: string; color: string }> = {
  user: { label: "个人全局", color: "blue" },
  user_farm: { label: "当前农场", color: "cyan" },
};

export const MEMORY_KIND_META: Record<MemoryKind, { label: string; color: string }> = {
  preference: { label: "偏好", color: "geekblue" },
  habit: { label: "习惯", color: "purple" },
  episode: { label: "经历", color: "default" },
};

export const MEMORY_SOURCE_META: Record<MemorySourceType, { label: string; color: string }> = {
  explicit: { label: "手动保存", color: "blue" },
  inferred: { label: "自动学习", color: "purple" },
};

export const MEMORY_STATUS_META: Record<MemoryStatus, { label: string; color: string }> = {
  active: { label: "生效中", color: "green" },
  candidate: { label: "待确认", color: "gold" },
  superseded: { label: "已替代", color: "default" },
  expired: { label: "已过期", color: "default" },
  deleted: { label: "已删除", color: "red" },
};

export const MEMORY_SCOPE_FILTERS = [
  { value: "user", label: "个人全局" },
  { value: "user_farm", label: "当前农场" },
];

export const MEMORY_KIND_FILTERS = [
  { value: "preference", label: "偏好" },
  { value: "habit", label: "习惯" },
  { value: "episode", label: "经历" },
];

export const MEMORY_STATUS_FILTERS = [
  { value: "active", label: "生效中" },
  { value: "candidate", label: "待确认" },
  { value: "expired", label: "已过期" },
];
