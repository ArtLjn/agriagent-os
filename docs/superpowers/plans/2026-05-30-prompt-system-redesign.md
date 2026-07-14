# Prompt System Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将单体 `base.j2` 拆分为可组合的 snippet，新增 `PromptComposer` 按场景组合渲染，消除冗余工具路由规则和矛盾优先级标注。

**Architecture:** 新增 `PromptComposer` 层位于 `PromptRegistry`/`PromptRenderer` 之上。Snippet 文件存放在 `prompts/snippets/` 目录，按 `p1-p4` 前缀标记优先级。场景组合配置在 `config.yaml` 的 `compositions` 段。现有 5 个 `render_prompt` 调用点改为 `composer.compose`。

**Tech Stack:** Python 3.11 / Jinja2 / YAML / pytest

---

## File Structure

| 操作 | 文件 | 职责 |
|------|------|------|
| Create | `prompts/snippets/p1-language.j2` | P1 语言规则 snippet |
| Create | `prompts/snippets/p1-tool-guardrails.j2` | P1 工具调用安全护栏 snippet |
| Create | `prompts/snippets/p2-role.j2` | P2 角色定义 snippet |
| Create | `prompts/snippets/p2-capability.j2` | P2 能力范围 snippet |
| Create | `prompts/snippets/p3-format.j2` | P3 回复格式 snippet |
| Create | `prompts/snippets/p3-style.j2` | P3 回复风格 snippet |
| Create | `prompts/snippets/p4-context.j2` | P4 动态上下文（时间/用户信息）snippet |
| Modify | `prompts/config.yaml` | 新增 `compositions` 段 |
| Create | `app/agent/prompt_composer.py` | PromptComposer 类 |
| Modify | `app/agent/graph.py:228-237` | system_base 调用改为 composer |
| Modify | `app/agent/report.py:34-36` | report 调用改为 composer |
| Modify | `app/api/cost.py:121-126` | cost_parse 调用改为 composer |
| Modify | `app/api/crop.py:124-128` | crop_template_parse 调用改为 composer |
| Modify | `app/api/cycle.py:153-157` | cycle_parse 调用改为 composer |
| Modify | `app/main.py:43,75-77` | 初始化 PromptComposer |
| Modify | `prompts/base.j2` | 移除矛盾标注（保留为 legacy 别名） |
| Modify | `prompts/cost_parse.j2` | 移除重复语言规则 |
| Modify | `prompts/crop_template_parse.j2` | 移除重复语言规则 |
| Modify | `prompts/cycle_parse.j2` | 移除重复语言规则 |
| Create | `tests/test_prompt_composer.py` | Composer 单元测试 |
| Modify | `tests/test_prompt_registry.py` | 适配 Composer |

---

### Task 1: 创建 Snippet 文件

**Files:**
- Create: `backend/prompts/snippets/p1-language.j2`
- Create: `backend/prompts/snippets/p1-tool-guardrails.j2`
- Create: `backend/prompts/snippets/p2-role.j2`
- Create: `backend/prompts/snippets/p2-capability.j2`
- Create: `backend/prompts/snippets/p3-format.j2`
- Create: `backend/prompts/snippets/p3-style.j2`
- Create: `backend/prompts/snippets/p4-context.j2`

- [ ] **Step 1: 创建 snippets 目录和 p1-language.j2**

```bash
mkdir -p backend/prompts/snippets
```

`prompts/snippets/p1-language.j2`:
```
【语言规则】
- 你必须全程使用中文回答，禁止输出任何英文单词或英文句子。
- 农业专业术语中的英文品种名（如 Watermelon、Tomato）允许保留英文。
- 数字、单位符号（如 ℃、kg、亩）不受此限制。
- 如果检测到英文输出，系统将自动拦截并提示用户重试。
```

- [ ] **Step 2: 创建 p1-tool-guardrails.j2**

`prompts/snippets/p1-tool-guardrails.j2`:
```
【安全护栏】
- 禁止凭记忆回答天气、成本、农事记录、茬口状态等实时数据，必须调用工具。
- 禁止假装已执行操作（如说"已记账""已创建茬口"），所有操作必须通过工具调用完成。
- 遇到上述信息时，必须先调用对应工具获取真实数据，再回答。
- 如果不确定信息是否最新，一律调用工具确认。
- 回答要简洁明了，适合农民理解。
```

- [ ] **Step 3: 创建 p2-role.j2**

`prompts/snippets/p2-role.j2`:
```
【角色定义】
你是一位经验丰富的农业技术顾问，擅长西瓜、豆角、番茄等作物的种植管理。你了解农事操作、病虫害防治、施肥浇水、成本收支等农业知识。
```

- [ ] **Step 4: 创建 p2-capability.j2**

`prompts/snippets/p2-capability.j2`:
```
【能力范围】
你具备以下工具调用能力：
- 查询天气预报和灾害预警
- 获取当前农场综合状态（茬口、农事、花费、天气）
```

- [ ] **Step 5: 创建 p3-format.j2**

`prompts/snippets/p3-format.j2`:
```
【回复格式】
- 称呼用户为「{{ display_name }}」，但不要在回复开头加任何自称或称呼前缀（如"系统管理员:"、"农业顾问:"等），直接回答内容
- 每条建议/操作不超过2行
- 总共不超过5条
- 先说结论，再说原因（如：明天降温12° → 你那西瓜正伸蔓期怕冻）
- 禁止铺垫、寒暄、总结段
- 用「你」不用「您」，口语化
```

- [ ] **Step 6: 创建 p3-style.j2**

`prompts/snippets/p3-style.j2`:
```
【回复风格】
- 每条建议加 emoji 前缀（🌱💡⚠️📊💰等），让内容更醒目
- 输出纯文本，不要使用 Markdown 格式（如列表、加粗、表格、代码块等）
- 用简短段落或换行分隔内容，每段一个要点
- 用扁平短句表达，不要写长段落
```

- [ ] **Step 7: 创建 p4-context.j2**

`prompts/snippets/p4-context.j2`:
```
{% if current_date %}
【时间信息】
今天是 {{ current_date }}，星期{{ current_weekday }}。当前时间 {{ current_time }}。
{% endif %}

{% if farm_location or current_season %}
【用户信息】
<user_context>
  {% if farm_location %}<location>{{ farm_location }}</location>{% endif %}
  {% if display_name %}<name>{{ display_name }}</name>{% endif %}
  {% if current_season %}<season>{{ current_season }}</season>{% endif %}
</user_context>
{% endif %}
```

- [ ] **Step 8: 提交 snippets**

```bash
git add backend/prompts/snippets/
git commit -m "feat(prompt): 创建可组合 snippet 文件（P1-P4）"
```

---

### Task 2: 更新 config.yaml 添加 compositions 配置

**Files:**
- Modify: `backend/prompts/config.yaml`

- [ ] **Step 1: 写入 compositions 配置**

在 `config.yaml` 末尾追加 `compositions` 段：

```yaml
version: "1.0"
defaults:
  system_base: base
  cost_parse: cost_parse
  report: report
  crop_template_parse: crop_template_parse
templates:
  base:
    file: base.j2
    description: "基础 system prompt，含语言规则置顶"
  cost_parse:
    file: cost_parse.j2
    description: "记账解析 prompt，注入当前日期"
  report:
    file: report.j2
    description: "报告生成 prompt"
  crop_template_parse:
    file: crop_template_parse.j2
    description: "作物模板解析 prompt，从自然语言描述提取结构化作物数据"
  cycle_parse:
    file: cycle_parse.j2
    description: "茬口解析 prompt，从自然语言描述提取结构化种植计划"
compositions:
  system_base:
    snippets:
      - p1-language
      - p1-tool-guardrails
      - p2-role
      - p2-capability
      - p3-format
      - p3-style
      - p4-context
    separator: "\n\n"
  cost_parse:
    snippets:
      - p1-language
    template: cost_parse
    separator: "\n\n"
  crop_template_parse:
    snippets:
      - p1-language
    template: crop_template_parse
    separator: "\n\n"
  cycle_parse:
    snippets:
      - p1-language
    template: cycle_parse
    separator: "\n\n"
  report:
    snippets:
      - p1-language
    template: report
    separator: "\n\n"
```

注意：`cost_parse`/`crop_template_parse`/`cycle_parse`/`report` 四个场景使用 `snippets + template` 模式 — 先渲染 snippets 片段，再拼接原有的 task-specific 模板。这样只需在 `snippets` 中引用 `p1-language` 即可消除各模板中重复的语言规则块。

- [ ] **Step 2: 提交 config.yaml**

```bash
git add backend/prompts/config.yaml
git commit -m "feat(prompt): config.yaml 新增 compositions 场景组合配置"
```

---

### Task 3: 实现 PromptComposer（TDD）

**Files:**
- Create: `backend/tests/test_prompt_composer.py`
- Create: `backend/app/agent/prompt_composer.py`

- [ ] **Step 1: 写 PromptComposer 的失败测试**

`tests/test_prompt_composer.py`:
```python
"""PromptComposer 测试。"""

from datetime import date
from pathlib import Path

import pytest

from app.agent.prompt_composer import PromptComposer
from app.agent.prompt_registry import PromptRegistry

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@pytest.fixture()
def _composer():
    """从 prompts/ 目录初始化的 PromptComposer。"""
    reg = PromptRegistry()
    reg.reload(_PROMPTS_DIR)
    return PromptComposer(reg, _PROMPTS_DIR)


class TestComposerLoadSnippets:
    """Snippet 加载测试。"""

    def test_loads_all_p1_to_p4_snippets(self, _composer):
        """Composer 加载 snippets/ 目录下所有 snippet。"""
        names = _composer.list_snippets()
        assert "p1-language" in names
        assert "p1-tool-guardrails" in names
        assert "p2-role" in names
        assert "p4-context" in names

    def test_snippet_file_not_found_logs_warning(self):
        """snippets/ 目录不存在时不崩溃，记录警告。"""
        reg = PromptRegistry()
        composer = PromptComposer(reg, Path("/nonexistent"))
        assert composer.list_snippets() == []


class TestComposerCompose:
    """场景组合测试。"""

    def test_system_base_compose(self, _composer):
        """system_base 场景组合包含所有必要段。"""
        result = _composer.compose(
            "system_base",
            variables={"display_name": "老李", "farm_location": "苏州", "current_season": "夏季"},
            current_date=date(2026, 5, 29),
        )
        assert "【语言规则】" in result
        assert "【安全护栏】" in result
        assert "【角色定义】" in result
        assert "老李" in result
        assert "苏州" in result
        assert "2026-05-29" in result

    def test_system_base_no_hardcoded_tool_names(self, _composer):
        """system_base 组合结果不含具体工具名。"""
        result = _composer.compose(
            "system_base",
            variables={"display_name": "农友"},
            current_date=date(2026, 5, 29),
        )
        assert "get_farm_status" not in result
        assert "weather" not in result
        assert "最高优先级" not in result

    def test_cost_parse_compose(self, _composer):
        """cost_parse 场景组合：snippet + template。"""
        result = _composer.compose(
            "cost_parse",
            variables={"description": "人工费300"},
            current_date=date(2026, 5, 29),
        )
        assert "【语言规则】" in result
        assert "人工费300" in result
        assert "record_type" in result

    def test_cost_parse_no_duplicate_language_rules(self, _composer):
        """cost_parse 组合结果中语言规则只出现一次（去重）。"""
        result = _composer.compose(
            "cost_parse",
            variables={"description": "测试"},
            current_date=date(2026, 5, 29),
        )
        assert result.count("【语言规则】") == 1

    def test_unknown_scene_raises(self, _composer):
        """未配置的场景抛出 KeyError。"""
        with pytest.raises(KeyError, match="nonexistent"):
            _composer.compose("nonexistent")


class TestPriorityStack:
    """Priority Stack 排序测试。"""

    def test_p1_before_p3(self, _composer):
        """P1 Safety 段在 P3 Format 段之前。"""
        result = _composer.compose(
            "system_base",
            variables={"display_name": "农友"},
            current_date=date(2026, 5, 29),
        )
        p1_pos = result.index("【语言规则】")
        p3_pos = result.index("【回复格式】")
        assert p1_pos < p3_pos

    def test_p2_before_p4(self, _composer):
        """P2 Accuracy 段在 P4 Context 段之前。"""
        result = _composer.compose(
            "system_base",
            variables={"display_name": "农友", "farm_location": "苏州"},
            current_date=date(2026, 5, 29),
        )
        p2_pos = result.index("【角色定义】")
        p4_pos = result.index("【时间信息】")
        assert p2_pos < p4_pos
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_prompt_composer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.agent.prompt_composer'`

- [ ] **Step 3: 实现 PromptComposer**

`app/agent/prompt_composer.py`:
```python
"""Prompt 组合器 — 按场景组合 snippet 片段渲染最终 prompt。"""

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from jinja2 import Template

if TYPE_CHECKING:
    from app.agent.prompt_registry import PromptRegistry

from app.agent.prompt_renderer import _build_builtin_vars

logger = logging.getLogger(__name__)

_PRIORITY_RE = re.compile(r"^p(\d)-")

_COMPOSITIONS_KEY = "compositions"


class PromptComposer:
    """按场景组合 snippet 片段渲染最终 prompt。"""

    def __init__(self, registry: "PromptRegistry", prompts_dir: Path):
        self._registry = registry
        self._prompts_dir = prompts_dir
        self._snippets: dict[str, str] = {}
        self._compositions: dict[str, dict] = {}
        self._load_snippets()
        self._load_compositions()

    def _load_snippets(self) -> None:
        snippets_dir = self._prompts_dir / "snippets"
        if not snippets_dir.exists():
            logger.warning("snippets 目录不存在: %s", snippets_dir)
            return
        for f in snippets_dir.glob("*.j2"):
            name = f.stem
            self._snippets[name] = f.read_text()
        logger.info("Snippet 加载完成 | count=%d", len(self._snippets))

    def _load_compositions(self) -> None:
        config_path = self._prompts_dir / "config.yaml"
        if not config_path.exists():
            return
        config = yaml.safe_load(config_path.read_text()) or {}
        self._compositions = config.get(_COMPOSITIONS_KEY, {})
        logger.info("Compositions 加载完成 | count=%d", len(self._compositions))

    def list_snippets(self) -> list[str]:
        return sorted(self._snippets.keys())

    def compose(
        self,
        scene: str,
        variables: dict | None = None,
        *,
        current_date=None,
    ) -> str:
        if scene not in self._compositions:
            raise KeyError(f"场景未配置: {scene}")
        comp = self._compositions[scene]
        snippet_names = comp.get("snippets", [])
        separator = comp.get("separator", "\n\n")
        template_name = comp.get("template")

        builtin_vars = _build_builtin_vars(current_date)
        ctx = {**builtin_vars, **(variables or {})}

        parts = []
        seen = set()
        for name in snippet_names:
            if name in seen:
                continue
            seen.add(name)
            content = self._snippets.get(name)
            if content is None:
                logger.warning("Snippet 不存在: %s", name)
                continue
            rendered = Template(content).render(ctx)
            parts.append((name, rendered))

        parts.sort(key=lambda x: self._priority_of(x[0]))

        result = separator.join(p[1] for p in parts)

        if template_name:
            from app.agent.prompt_renderer import render_prompt

            template_text = render_prompt(
                template_name,
                variables=variables,
                registry=self._registry,
                current_date=current_date,
            )
            result = result + separator + template_text

        return result

    @staticmethod
    def _priority_of(name: str) -> int:
        m = _PRIORITY_RE.match(name)
        if m:
            return int(m.group(1))
        return 99


__all__ = ["PromptComposer"]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_prompt_composer.py -v`
Expected: All tests PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/agent/prompt_composer.py backend/tests/test_prompt_composer.py
git commit -m "feat(prompt): 实现 PromptComposer（snippet 组合 + priority stack）"
```

---

### Task 4: 切换调用点 — graph.py 和 report.py

**Files:**
- Modify: `backend/app/agent/graph.py:24-25,228-237`
- Modify: `backend/app/agent/report.py:10-11,34-36`

- [ ] **Step 1: 修改 graph.py 导入和调用**

在 `graph.py` 顶部（约第 24-25 行）：
- 保留 `from app.agent.prompt_registry import get_registry`
- 新增 `from app.agent.prompt_composer import PromptComposer`

替换 `graph.py` 第 228-237 行：
```python
    # 原来:
    # system_text = render_prompt(
    #     "system_base",
    #     variables={...},
    #     registry=get_registry(),
    #     current_date=current_date,
    # )
    # 改为:
    composer = PromptComposer(get_registry(), get_registry()._load_from_dir.__self__ and _get_prompts_dir())
```

等一下，这里需要确认 `prompts_dir` 的来源。看 `main.py` 中 `settings.prompts_dir`：

查看 `app/core/config.py` 中 `prompts_dir` 的定义：

```bash
grep -n "prompts_dir" backend/app/core/config.py
```

通常 prompts_dir 是 settings 属性。需要在 graph.py 中获取这个路径。

最简洁的方式：让 PromptComposer 自身记住 prompts_dir，通过全局单例暴露：

在 `prompt_composer.py` 底部新增全局单例和获取函数：

```python
_composer: PromptComposer | None = None


def get_composer() -> PromptComposer:
    global _composer
    if _composer is None:
        from app.agent.prompt_registry import get_registry
        from app.core.config import get_settings

        settings = get_settings()
        _composer = PromptComposer(get_registry(), settings.prompts_dir)
    return _composer
```

这样调用点只需：
```python
from app.agent.prompt_composer import get_composer

composer = get_composer()
system_text = composer.compose(
    "system_base",
    variables={
        "display_name": display_name,
        "farm_location": farm_location,
        "current_season": current_season,
    },
    current_date=current_date,
)
```

**实际修改 `graph.py`:**

1. 在文件顶部导入区域新增：
```python
from app.agent.prompt_composer import get_composer
```

2. 可以移除以下导入（如果文件中无其他使用处，需检查）：
```python
from app.agent.prompt_renderer import render_prompt  # 改为 composer
```

3. 将第 228-237 行替换为：
```python
    system_text = get_composer().compose(
        "system_base",
        variables={
            "display_name": display_name,
            "farm_location": farm_location,
            "current_season": current_season,
        },
        current_date=current_date,
    )
```

注意：检查 `render_prompt` 和 `get_registry` 在 graph.py 中是否还有其他使用处。通过之前搜索确认 `render_prompt` 只在第 228 行使用一次。`get_registry` 也只在第 235 行用一次。所以两个导入都可以移除。

- [ ] **Step 2: 修改 report.py**

1. 替换导入：移除 `from app.agent.prompt_renderer import render_prompt`，新增 `from app.agent.prompt_composer import get_composer`
2. 保留 `from app.agent.prompt_registry import get_registry`（如果其他地方还用的话——检查 report.py，第 10 行导入 get_registry 但只在第 35 行用，改后可移除）
3. 将第 34-36 行替换为：
```python
    system_text = get_composer().compose(
        "report", current_date=current_date
    )
```

- [ ] **Step 3: 运行 agent 相关测试**

Run: `cd backend && .venv/bin/python -m pytest tests/test_agent_service.py tests/test_function_calling_e2e.py tests/test_context_engineering_e2e.py -v --tb=short`
Expected: All PASS

- [ ] **Step 4: 提交**

```bash
git add backend/app/agent/graph.py backend/app/agent/report.py
git commit -m "refactor(agent): graph.py 和 report.py 切换到 PromptComposer"
```

---

### Task 5: 切换调用点 — API 层 cost.py / crop.py / cycle.py

**Files:**
- Modify: `backend/app/api/cost.py:10,121-126`
- Modify: `backend/app/api/crop.py:9-10,124-128`
- Modify: `backend/app/api/cycle.py:10-11,153-157`

- [ ] **Step 1: 修改 cost.py**

替换导入（第 10 行）：
```python
# 移除:
# from app.agent.prompt_renderer import render_prompt
# 新增:
from app.agent.prompt_composer import get_composer
```

保留 `from app.agent.prompt_registry import get_registry`（需检查是否有其他使用——通过搜索确认 cost.py 中 get_registry 只在第 124 行用一次，可以移除）。

将第 121-126 行替换为：
```python
    prompt = get_composer().compose(
        "cost_parse",
        {"description": req.description},
        current_date=current_date,
    )
```

- [ ] **Step 2: 修改 crop.py**

同 cost.py 模式：
- 移除 `from app.agent.prompt_renderer import render_prompt` 和 `from app.agent.prompt_registry import get_registry`
- 新增 `from app.agent.prompt_composer import get_composer`
- 将第 124-128 行替换为：
```python
    prompt = get_composer().compose(
        "crop_template_parse",
        {"description": req.description},
    )
```

- [ ] **Step 3: 修改 cycle.py**

同 cost.py 模式：
- 移除 `from app.agent.prompt_renderer import render_prompt` 和 `from app.agent.prompt_registry import get_registry`
- 新增 `from app.agent.prompt_composer import get_composer`
- 将第 153-157 行替换为：
```python
    prompt = get_composer().compose(
        "cycle_parse",
        {"description": req.description, "templates": template_list, "today": today},
    )
```

- [ ] **Step 4: 运行 API 层测试**

Run: `cd backend && .venv/bin/python -m pytest tests/test_cost_category_service.py tests/test_crop.py tests/test_cost_delete.py -v --tb=short`
Expected: 检查结果。注意：有些测试可能因数据库集成问题失败（之前就有这些失败），但不应出现新的 ImportError。

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/cost.py backend/app/api/crop.py backend/app/api/cycle.py
git commit -m "refactor(api): cost/crop/cycle 切换到 PromptComposer"
```

---

### Task 6: 更新 main.py 初始化 Composer

**Files:**
- Modify: `backend/app/main.py:43,75-77`

- [ ] **Step 1: 在 main.py 启动时初始化 Composer**

当前第 43 行：`from app.agent.prompt_registry import get_registry`
第 75-77 行：
```python
    registry = get_registry()
    registry.reload(settings.prompts_dir)
    logger.info("Prompt 模板已加载 | dir=%s", settings.prompts_dir)
```

改为：
```python
    registry = get_registry()
    registry.reload(settings.prompts_dir)
    logger.info("Prompt 模板已加载 | dir=%s", settings.prompts_dir)

    # 初始化 PromptComposer 全局单例
    from app.agent.prompt_composer import get_composer
    get_composer()
    logger.info("PromptComposer 初始化完成")
```

这样 `get_composer()` 首次调用时通过全局单例创建 Composer，后续调用直接复用。

- [ ] **Step 2: 提交**

```bash
git add backend/app/main.py
git commit -m "feat(main): 启动时初始化 PromptComposer 全局单例"
```

---

### Task 7: 清理各 .j2 模板中的重复语言规则块

**Files:**
- Modify: `backend/prompts/cost_parse.j2:1-3`
- Modify: `backend/prompts/crop_template_parse.j2:1-5`
- Modify: `backend/prompts/cycle_parse.j2:1-3`

- [ ] **Step 1: 清理 cost_parse.j2**

移除第 1-3 行的语言规则块：
```
【语言规则】（最高优先级）
- 你必须全程使用中文回答，禁止输出任何英文单词或英文句子。
- 只返回 JSON，不要输出任何其他文字、解释或 markdown 格式。
```

替换为：
```
【输出规则】
- 只返回 JSON，不要输出任何其他文字、解释或 markdown 格式。
```

因为语言规则（"全程中文"）已通过 Composer 的 `p1-language` snippet 注入，不需要在模板中重复。但 JSON 输出约束是 cost_parse 特有的，保留。

- [ ] **Step 2: 清理 crop_template_parse.j2**

移除第 1-5 行：
```
【语言规则】（最高优先级）
- 你必须全程使用中文回答，禁止输出任何英文单词或英文句子。
- 农业专业术语中的英文品种名允许保留英文。
- 数字、单位符号（如 ℃、kg、亩）不受此限制。
- 如果检测到英文输出，系统将自动拦截并提示用户重试。
```

这些全部由 `p1-language` snippet 覆盖。直接删除。

- [ ] **Step 3: 清理 cycle_parse.j2**

移除第 1-3 行：
```
【语言规则】（最高优先级）
- 你必须全程使用中文回答，禁止输出任何英文单词或英文句子。
- 数字、日期格式、单位符号不受此限制。
```

由 `p1-language` snippet 覆盖。直接删除。

- [ ] **Step 4: 运行全量测试确认无回归**

Run: `cd backend && .venv/bin/python -m pytest tests/test_prompt_composer.py tests/test_context_engineering_e2e.py tests/test_prompt_registry.py tests/test_function_calling_e2e.py tests/test_agent_service.py -v --tb=short`
Expected: All PASS

- [ ] **Step 5: 提交**

```bash
git add backend/prompts/cost_parse.j2 backend/prompts/crop_template_parse.j2 backend/prompts/cycle_parse.j2
git commit -m "refactor(prompt): 移除各模板中重复的语言规则块（由 Composer snippet 覆盖）"
```

---

### Task 8: 更新现有测试适配 Composer

**Files:**
- Modify: `backend/tests/test_prompt_registry.py`

- [ ] **Step 1: 更新 test_prompt_registry.py**

`test_system_base_prompt_contains_tool_calling_rule` 测试（第 10-19 行）检查 base.j2 原始文件中包含"禁止凭记忆回答"。这个测试仍然有效——因为 base.j2 仍然存在（作为 legacy）且包含该文本。

但更准确的测试应该验证 Composer 组合后的结果。更新此测试为检查 snippet 文件：

```python
def test_tool_guardrails_snippet_contains_hard_constraint():
    """p1-tool-guardrails snippet 包含工具调用硬约束。"""
    from pathlib import Path

    prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
    snippet = prompts_dir / "snippets" / "p1-tool-guardrails.j2"
    if snippet.exists():
        content = snippet.read_text()
        assert "禁止凭记忆回答" in content
        assert "必须调用工具" in content
```

- [ ] **Step 2: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_prompt_registry.py tests/test_prompt_composer.py tests/test_context_engineering_e2e.py -v --tb=short`
Expected: All PASS

- [ ] **Step 3: 提交**

```bash
git add backend/tests/test_prompt_registry.py
git commit -m "test(prompt): 更新测试适配 snippet 架构"
```

---

### Task 9: 更新文档

**Files:**
- Modify: `docs/architecture/backend-architecture.md`（如果存在）

- [ ] **Step 1: 更新架构文档中 Prompt 管理模块描述**

找到 `docs/architecture/backend-architecture.md` 中关于 prompt 管理的章节，更新为描述新的 Composer + Snippet 架构。关键变更：
- 新增 `prompt_composer.py` 到模块清单
- 新增 `prompts/snippets/` 目录描述
- 更新请求流转图中的 prompt 渲染步骤

- [ ] **Step 2: 提交**

```bash
git add docs/architecture/backend-architecture.md
git commit -m "docs: 更新架构文档，反映 PromptComposer + Snippet 架构"
```

---

### Task 10: 最终集成验证

**Files:**
- 无新增文件

- [ ] **Step 1: 运行全量 prompt/tool/agent 相关测试**

Run: `cd backend && .venv/bin/python -m pytest tests/test_prompt_composer.py tests/test_prompt_registry.py tests/test_context_engineering_e2e.py tests/test_function_calling_e2e.py tests/test_agent_service.py tests/test_tool_selector.py tests/test_tool_chain_map.py tests/core/test_prompt_renderer.py -v --tb=short`
Expected: All PASS

- [ ] **Step 2: 检查无残留的 render_prompt 调用（源码中）**

Run: `grep -rn "render_prompt" backend/app/ --include="*.py"`
Expected: 只出现在 `prompt_renderer.py`（定义）和 `prompt_composer.py`（内部调用）。不应出现在 `graph.py`、`report.py`、`cost.py`、`crop.py`、`cycle.py` 中。

- [ ] **Step 3: 确认 prompts/ 目录结构正确**

Run: `find backend/prompts -type f | sort`
Expected 输出应包含：
```
backend/prompts/base.j2
backend/prompts/config.yaml
backend/prompts/cost_parse.j2
backend/prompts/crop_template_parse.j2
backend/prompts/cycle_parse.j2
backend/prompts/report.j2
backend/prompts/snippets/p1-language.j2
backend/prompts/snippets/p1-tool-guardrails.j2
backend/prompts/snippets/p2-capability.j2
backend/prompts/snippets/p2-role.j2
backend/prompts/snippets/p3-format.j2
backend/prompts/snippets/p3-style.j2
backend/prompts/snippets/p4-context.j2
```
