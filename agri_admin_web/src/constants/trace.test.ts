import { describe, expect, it } from 'vitest';

import { getNodeColor } from './trace';

describe('trace 节点颜色', () => {
  it('将细分 trace 类型归一到图例语义颜色', () => {
    expect(getNodeColor('skill_router')).toBe(getNodeColor('routing'));
    expect(getNodeColor('tool_call_forced')).toBe(getNodeColor('routing'));
    expect(getNodeColor('context_build')).toBe(getNodeColor('prompt_render'));
    expect(getNodeColor('prompt_budget')).toBe(getNodeColor('prompt_render'));
  });
});
