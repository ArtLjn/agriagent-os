/**
 * Trace 节点类型颜色映射。
 * 与 Gantt 图、trace 列表共用。
 */
export const NODE_TYPE_COLORS: Record<string, string> = {
  routing: '#e0a23c',        // 琥珀 — 路由决策
  catalog_recall: '#e0a23c', // 琥珀 — Skill 候选
  prompt_render: '#4f8cff',  // 蓝色 — Prompt 渲染
  llm_call: '#a78bfa',       // 紫色 — LLM 调用
  skill_call: '#3fae72',     // 绿色 — Skill 执行
  final_context: '#22b8cf',  // 青色 — Final 上下文边界
  output_guard: '#e0a23c',   // 琥珀 — 输出防泄漏
  error: '#e5534b',          // 红色 — 错误节点
};

const NODE_TYPE_ALIASES: Record<string, string> = {
  skill_router: 'routing',
  tool_call_forced: 'routing',
  context_build: 'prompt_render',
  prompt_budget: 'prompt_render',
};

export const NODE_TYPE_LABELS: Record<string, string> = {
  routing: '路由决策',
  catalog_recall: 'Skill 候选',
  prompt_render: 'Prompt 渲染',
  llm_call: 'LLM 调用',
  skill_call: 'Skill 执行',
  final_context: 'Final 上下文',
  output_guard: '输出防泄漏',
  error: '错误',
};

function normalizeNodeType(nodeType: string): string {
  return NODE_TYPE_COLORS[nodeType] ? nodeType : NODE_TYPE_ALIASES[nodeType] || nodeType;
}

/** 获取节点类型的颜色，未知类型返回默认灰色 */
export function getNodeColor(nodeType: string): string {
  return NODE_TYPE_COLORS[normalizeNodeType(nodeType)] || '#93a89b';
}

/** 获取节点类型的中文标签 */
export function getNodeLabel(nodeType: string): string {
  return NODE_TYPE_LABELS[normalizeNodeType(nodeType)] || nodeType;
}
