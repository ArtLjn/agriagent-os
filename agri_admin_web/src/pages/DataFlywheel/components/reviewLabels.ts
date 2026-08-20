export const qualityLabelOptions = [
  { value: 'good_reply', label: '回复正确' },
  { value: 'bad_reply', label: '回复质量差' },
  { value: 'wrong_tool_selection', label: '工具选择错误' },
  { value: 'tool_parameter_mismatch', label: '工具参数不匹配' },
  { value: 'pending_missed', label: '缺少确认' },
  { value: 'hallucinated_execution', label: '幻觉执行' },
  { value: 'tool_error_ignored', label: '忽略工具失败' },
  { value: 'off_topic', label: '答非所问' },
  { value: 'sensitive_info_leak', label: '敏感信息泄露' },
  { value: 'missing_wage', label: '缺少工资' },
  { value: 'disabled_worker_used', label: '使用禁用工人' },
  { value: 'unclear_intent', label: '意图不清' },
  { value: 'not_actionable', label: '暂不处理' },
  { value: 'needs_regression', label: '需要回归用例' },
];

export const missingEvidenceOptions = [
  { value: 'event_log', label: '事件日志' },
  { value: 'chat_messages', label: '对话消息' },
  { value: 'router_decision', label: '路由决策' },
  { value: 'tool_result', label: '工具结果' },
  { value: 'pending_lifecycle', label: '确认流程' },
  { value: 'trace', label: 'Trace 链路' },
  { value: 'db_diff', label: '数据变更' },
  { value: 'backfilled_event', label: '回填事件' },
];

export const fixTargetOptions = [
  { value: 'prompt', label: '提示词' },
  { value: 'router', label: '路由' },
  { value: 'tool', label: '工具' },
  { value: 'pending', label: '确认流程' },
  { value: 'data', label: '数据' },
  { value: 'policy', label: '策略' },
  { value: 'unknown', label: '待判断' },
  { value: 'manual_triage', label: '人工分流' },
];

const statusText: Record<string, string> = {
  unreviewed: '未审核',
  ready_for_review: '可审核',
  needs_evidence: '需补证据',
  accepted: '已采纳',
  rejected: '已驳回',
  not_actionable: '暂不处理',
  pending: '待确认',
  labeled: '已标注',
  unlabeled: '未标注',
  draft: '草稿',
  exported: '已导出',
  export_failed: '导出失败',
  verification_failed: '验证失败',
  resolved: '已修复',
  discarded: '已丢弃',
};

const evidenceStatusText: Record<string, string> = {
  ready_for_review: '可审核',
  needs_evidence: '需补证据',
  present: '已具备',
  missing: '缺失',
  needs_human: '需人工确认',
  available: '已具备',
};

const signalText: Record<string, string> = {
  rule: '规则命中',
  judge: 'AI 预判',
  context_analyzer: '上下文分析',
  evaluation_failed: '评测回流',
  manual_triage: '人工分流',
};

const actionText: Record<string, string> = {
  review_chain: '立即审核',
  collect_evidence: '补齐证据',
  export_repair_pack: '导出修复包',
  create_regression: '生成回归',
};

const roleText: Record<string, string> = {
  trigger: '触发轮',
  context: '上下文',
  result: '结果轮',
  unrelated: '无关轮',
};

const eventLogStatusText: Record<string, string> = {
  available: '事件可用',
  missing: '事件缺失',
  unbound: '未绑定事件',
};

const targetTypeLabels: Record<string, string> = {
  evaluation_replay: '评测回放',
  regression: '回归用例',
  sample: '样本',
  review_issue_chain: '问题链',
};

export function qualityLabelText(value: string): string {
  return qualityLabelOptions.find((item) => item.value === value)?.label ?? value;
}

export function evidenceKeyText(value: string): string {
  return missingEvidenceOptions.find((item) => item.value === value)?.label ?? value;
}

export function fixTargetText(value: string | null | undefined): string {
  if (!value) return '人工分流';
  return fixTargetOptions.find((item) => item.value === value)?.label ?? value;
}

export function reviewStatusText(value: string | null | undefined): string {
  if (!value) return '未审核';
  return statusText[value] ?? value;
}

export function evidenceStatusLabel(value: string | null | undefined): string {
  if (!value) return '未知';
  return evidenceStatusText[value] ?? value;
}

export function dominantSignalText(value: string | null | undefined): string {
  if (!value) return '未知来源';
  return signalText[value] ?? value;
}

export function nextActionText(value: string | null | undefined): string {
  if (!value) return '待处理';
  return actionText[value] ?? value;
}

export function timelineRoleText(value: string): string {
  return roleText[value] ?? value;
}

export function eventStatusText(value: string | null | undefined): string {
  if (!value) return '事件未知';
  return eventLogStatusText[value] ?? value;
}

export function targetTypeText(value: string | null | undefined): string {
  if (!value) return '未知目标';
  return targetTypeLabels[value] ?? value;
}
