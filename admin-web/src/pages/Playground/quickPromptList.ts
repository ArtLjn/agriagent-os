export interface QuickPrompt {
  key: string;
  icon: string;
  title: string;
  description: string;
  prompt: string;
}

export const QUICK_PROMPTS: QuickPrompt[] = [
  {
    key: 'cost',
    icon: '💰',
    title: '记一笔账',
    description: '触发 manage-cost 真实执行',
    prompt: '帮我记一笔：今天买了 200 元化肥',
  },
  {
    key: 'worker',
    icon: '👥',
    title: '添加工人',
    description: '触发 pending plan 二次确认',
    prompt: '帮我添加一个工人：张三，电话 13800000000',
  },
  {
    key: 'crop-cycle',
    icon: '🌱',
    title: '查看茬口',
    description: '测试只读查询与上下文累积',
    prompt: '我现在有哪些进行中的茬口？',
  },
  {
    key: 'work-order',
    icon: '📋',
    title: '创建工单',
    description: '测试多步骤复合技能链路',
    prompt: '给 2 号棚创建一个明天的浇水工单',
  },
  {
    key: 'weather',
    icon: '☀️',
    title: '查天气',
    description: '测试外部数据源接入',
    prompt: '明天天气怎么样？',
  },
  {
    key: 'search',
    icon: '🔍',
    title: '联网搜索',
    description: '测试 web_search 检索能力',
    prompt: '帮我搜一下番茄常见病害的防治方法',
  },
];
