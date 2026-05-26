/**
 * Trace 节点类型颜色映射。
 * 与 Gantt 图、trace 列表共用。
 */
export const NODE_TYPE_COLORS: Record<string, string> = {
  prompt_render: '#1890ff',  // 蓝色 — Prompt 渲染
  llm_call: '#722ed1',       // 紫色 — LLM 调用
  skill_call: '#52c41a',     // 绿色 — Skill 执行
  error: '#ff4d4f',          // 红色 — 错误节点
};

export const NODE_TYPE_LABELS: Record<string, string> = {
  prompt_render: 'Prompt 渲染',
  llm_call: 'LLM 调用',
  skill_call: 'Skill 执行',
  error: '错误',
};

/** 获取节点类型的颜色，未知类型返回默认灰色 */
export function getNodeColor(nodeType: string): string {
  return NODE_TYPE_COLORS[nodeType] || '#8b949e';
}

/** 获取节点类型的中文标签 */
export function getNodeLabel(nodeType: string): string {
  return NODE_TYPE_LABELS[nodeType] || nodeType;
}
