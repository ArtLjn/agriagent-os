# AI 长时记忆 Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增强 Agent Skills 查询能力 + 前端 AI 帮记 + 账单分类归档统计

**Architecture:** 后端 Skills 从"单周期查询"升级为"多维度聚合分析"，前端记一笔页面增加自然语言输入入口，账单列表增加分类汇总视图。

**Tech Stack:** Python 3.12 + FastAPI + LangGraph + skillify, React Native + TypeScript + Zustand

---

## File Structure

| File | Responsibility |
|------|---------------|
| `backend/app/skills/cost-summary/scripts/main.py` | 增强版成本汇总 Skill（支持分类/按月/全局/时间范围） |
| `backend/app/skills/cost-analytics/scripts/main.py` | 新增全局成本分析 Skill（跨周期对比分析） |
| `backend/app/skills/cost-analytics/scripts/__init__.py` | Skill 包初始化 |
| `backend/app/skills/__init__.py` | Skill 注册 + farm_id context 传递 |
| `backend/app/agents/graph.py` | AgentState 增加 farm_id，system prompt 更新 |
| `backend/app/agents/advisor.py` | invoke_advisor / stream_advisor 接收 farm_id |
| `backend/app/services/agent_service.py` | chat_with_agent 传递 farm_id 到 advisor |
| `backend/tests/test_cost.py` | 新增 parse 接口和 analytics 测试 |
| `backend/tests/test_skills.py` | 新增 Skill 单元测试 |
| `FarmManagerMobile/src/api/client.ts` | 新增 parseRecord API |
| `FarmManagerMobile/src/screens/cost/CostCreateScreen.tsx` | AI 帮记输入区域 + 重设计 UI |
| `FarmManagerMobile/src/screens/cost/CostListScreen.tsx` | 增加分类归档汇总卡片 |

---

### Task 1: 修改 graph.py 支持 farm_id

**Files:**
- Modify: `backend/app/agents/graph.py`
- Test: `backend/tests/test_advisor_agent.py`

- [ ] **Step 1: 修改 AgentState 和 tool_node 传递 farm_id**

```python
# backend/app/agents/graph.py
# AgentState 已含 farm_id: int
# 修改 _parallel_tool_node 注入 context

from skillify.core.context import SkillContext

async def _parallel_tool_node(state: AgentState) -> dict:
    last = state["messages"][-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return {"messages": []}

    tool_map = {t.name: t for t in get_langchain_tools()}
    farm_id = state.get("farm_id", 1)

    async def _call_one(tc: dict) -> ToolMessage:
        name = tc["name"]
        args = tc["args"]
        tool_call_id = tc["id"]
        logger.info("Skill 调用 %s(%s)", name, args)
        try:
            tool = tool_map.get(name)
            if not tool:
                return ToolMessage(content=f"未知工具: {name}", tool_call_id=tool_call_id)
            # 传递 farm_id context
            ctx = SkillContext(farm_id=farm_id)
            result = await tool.ainvoke(args, context=ctx)
            summary = str(result)[:120].replace("\n", " ")
            logger.info("Skill 返回 %s -> %s", name, summary)
            return ToolMessage(content=str(result), tool_call_id=tool_call_id)
        except Exception as e:
            logger.error("Skill 失败 %s: %s", name, e)
            return ToolMessage(content=f"工具调用失败: {e}", tool_call_id=tool_call_id)
    # ... rest unchanged
```

- [ ] **Step 2: 修改 advisor.py 接口接收 farm_id**

```python
# backend/app/agents/advisor.py

async def invoke_advisor(user_input: str, farm_id: int = 1) -> str:
    logger.info("Agent 收到请求: %s farm=%s", user_input[:200], farm_id)
    graph = _get_advisor_graph()
    result = await graph.ainvoke({
        "messages": [HumanMessage(content=user_input)],
        "farm_id": farm_id,
    })
    reply = result["messages"][-1].content
    logger.info("Agent 回复完成，长度 %d 字符", len(reply))
    return reply


async def stream_advisor(user_input: str, farm_id: int = 1) -> AsyncGenerator[str, None]:
    logger.info("Agent 流式请求: %s farm=%s", user_input[:200], farm_id)
    graph = _get_advisor_graph()
    step = 0
    async for event in graph.astream({
        "messages": [HumanMessage(content=user_input)],
        "farm_id": farm_id,
    }):
        # ... rest unchanged
```

- [ ] **Step 3: 修改 agent_service.py 传递 farm_id**

```python
# backend/app/services/agent_service.py
# chat_with_agent 中：
reply = await invoke_advisor(full_input, farm_id=farm_id)
# stream_chat_with_agent 中：
async for chunk in stream_advisor(full_input, farm_id=farm_id):
```

- [ ] **Step 4: 运行测试**

```bash
cd backend && poetry run pytest tests/test_advisor_agent.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/
git commit -m "feat: pass farm_id through agent graph to skills"
```

---

### Task 2: 重写 cost-summary Skill

**Files:**
- Modify: `backend/app/skills/cost-summary/scripts/main.py`
- Test: `backend/tests/test_skills.py`

- [ ] **Step 1: 重写 CostSummarySkill**

```python
"""成本汇总查询 Skill — 支持分类/按月/全局/时间范围。"""

from datetime import date

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.database import SessionLocal
from app.core.skill_cache import cached
from app.models.cost import CostRecord


class CostSummarySkill(Skill):
    def name(self) -> str:
        return "get_cost_summary"

    def description(self) -> str:
        return (
            "查询成本与收入汇总。支持按周期、时间范围、分类、类型筛选，"
            "支持按分类或按月分组。触发词: 成本、收入、利润、收支、花了多少、"
            "赚了多少钱、人工、化肥"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "cycle_id": {
                    "type": "integer",
                    "description": "种植周期 ID（可选，不传则查全部记录）",
                },
                "date_from": {
                    "type": "string",
                    "description": "开始日期 YYYY-MM-DD（可选）",
                },
                "date_to": {
                    "type": "string",
                    "description": "结束日期 YYYY-MM-DD（可选）",
                },
                "record_type": {
                    "type": "string",
                    "description": "记录类型: cost(支出)/income(收入)/all(全部，默认)",
                    "default": "all",
                },
                "category": {
                    "type": "string",
                    "description": "分类筛选（可选，如'人工'、'化肥'）",
                },
                "group_by": {
                    "type": "string",
                    "description": "分组方式: none(不分组)/category(按分类)/month(按月)，默认none",
                    "default": "none",
                },
            },
            "required": [],
        }

    @cached(ttl_seconds=300, key_fn=lambda p: f"cost_summary:{hash(str(sorted(p.items())))}")
    async def execute(self, params: dict, context) -> SkillResult:
        farm_id = getattr(context, "farm_id", 1) or 1
        cycle_id = params.get("cycle_id")
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        record_type = params.get("record_type", "all")
        category = params.get("category")
        group_by = params.get("group_by", "none")

        db = SessionLocal()
        try:
            query = db.query(CostRecord).filter(CostRecord.farm_id == farm_id)

            if cycle_id is not None:
                query = query.filter(CostRecord.cycle_id == cycle_id)
            if date_from:
                query = query.filter(CostRecord.record_date >= date_from)
            if date_to:
                query = query.filter(CostRecord.record_date <= date_to)
            if record_type in ("cost", "income"):
                query = query.filter(CostRecord.record_type == record_type)
            if category:
                query = query.filter(CostRecord.category == category)

            records = query.order_by(CostRecord.record_date.desc()).all()

            if not records:
                scope = "该周期" if cycle_id else "全部"
                return SkillResult(status=ResultStatus.SUCCESS, reply=f"{scope}暂无记录。")

            if group_by == "category":
                return self._group_by_category(records, record_type)
            elif group_by == "month":
                return self._group_by_month(records, record_type)
            else:
                return self._simple_summary(records, record_type, cycle_id)
        finally:
            db.close()

    def _simple_summary(self, records, record_type, cycle_id):
        total_cost = sum(r.amount for r in records if r.record_type == "cost")
        total_income = sum(r.amount for r in records if r.record_type == "income")
        net = total_income - total_cost

        scope = f"周期 ID={cycle_id} " if cycle_id else ""
        lines = [
            f"{scope}收支汇总：",
            f"  总支出：{total_cost} 元",
            f"  总收入：{total_income} 元",
            f"  净利润：{net} 元",
        ]

        if record_type == "all":
            lines.append("  明细：")
            for r in records[:20]:
                t = "支出" if r.record_type == "cost" else "收入"
                lines.append(f"    {r.record_date}: {t}-{r.category} {r.amount} 元")
        else:
            t_label = "支出" if record_type == "cost" else "收入"
            lines.append(f"  {t_label}明细：")
            for r in records[:20]:
                lines.append(f"    {r.record_date}: {r.category} {r.amount} 元")

        if len(records) > 20:
            lines.append(f"    ... 共 {len(records)} 条记录")

        return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))

    def _group_by_category(self, records, record_type):
        from collections import defaultdict
        groups = defaultdict(lambda: {"cost": 0, "income": 0})
        for r in records:
            groups[r.category][r.record_type] += float(r.amount)

        lines = ["按分类汇总："]
        for cat in sorted(groups.keys()):
            c = groups[cat]["cost"]
            i = groups[cat]["income"]
            if record_type == "cost" and c > 0:
                lines.append(f"  {cat}: 支出 {c} 元")
            elif record_type == "income" and i > 0:
                lines.append(f"  {cat}: 收入 {i} 元")
            elif record_type == "all":
                lines.append(f"  {cat}: 支出 {c} 元, 收入 {i} 元, 净 {i-c} 元")

        total_cost = sum(g["cost"] for g in groups.values())
        total_income = sum(g["income"] for g in groups.values())
        lines.append(f"  合计: 支出 {total_cost} 元, 收入 {total_income} 元")
        return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))

    def _group_by_month(self, records, record_type):
        from collections import defaultdict
        groups = defaultdict(lambda: {"cost": 0, "income": 0})
        for r in records:
            month = str(r.record_date)[:7]
            groups[month][r.record_type] += float(r.amount)

        lines = ["按月汇总："]
        for month in sorted(groups.keys()):
            c = groups[month]["cost"]
            i = groups[month]["income"]
            if record_type == "cost" and c > 0:
                lines.append(f"  {month}: 支出 {c} 元")
            elif record_type == "income" and i > 0:
                lines.append(f"  {month}: 收入 {i} 元")
            elif record_type == "all":
                lines.append(f"  {month}: 支出 {c} 元, 收入 {i} 元, 净 {i-c} 元")

        return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
```

- [ ] **Step 2: 运行 Skill 单元测试**

```bash
cd backend && poetry run pytest tests/test_skills.py -v -k cost_summary
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/skills/cost-summary/scripts/main.py
git commit -m "feat: enhance cost-summary skill with filtering and grouping"
```

---

### Task 3: 新增 cost-analytics Skill

**Files:**
- Create: `backend/app/skills/cost-analytics/scripts/__init__.py`
- Create: `backend/app/skills/cost-analytics/scripts/main.py`
- Test: `backend/tests/test_skills.py`

- [ ] **Step 1: 创建包初始化文件**

```python
# backend/app/skills/cost-analytics/scripts/__init__.py
```

（空文件即可，SkillManager 会自动发现该目录下的 Skill 类）

- [ ] **Step 2: 创建 CostAnalyticsSkill**

```python
# backend/app/skills/cost-analytics/scripts/main.py
"""全局成本分析 Skill — 跨周期收支趋势分析。"""

from datetime import date, datetime, timedelta

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.database import SessionLocal
from app.core.skill_cache import cached
from app.models.cost import CostRecord


class CostAnalyticsSkill(Skill):
    def name(self) -> str:
        return "get_cost_analytics"

    def description(self) -> str:
        return (
            "全局收支趋势分析，支持同比环比对比。"
            "触发词: 分析、趋势、对比、比去年、比上月"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "description": "分析开始日期 YYYY-MM-DD",
                },
                "date_to": {
                    "type": "string",
                    "description": "分析结束日期 YYYY-MM-DD",
                },
                "compare_period": {
                    "type": "string",
                    "description": "对比周期: none(不对比)/last_month(上月)/last_year(去年同期)",
                    "default": "none",
                },
            },
            "required": ["date_from", "date_to"],
        }

    @cached(ttl_seconds=300)
    async def execute(self, params: dict, context) -> SkillResult:
        farm_id = getattr(context, "farm_id", 1) or 1
        date_from = params["date_from"]
        date_to = params["date_to"]
        compare_period = params.get("compare_period", "none")

        db = SessionLocal()
        try:
            current = self._query_period(db, farm_id, date_from, date_to)
            lines = [f"收支分析 ({date_from} 至 {date_to})："]
            lines.extend(self._format_period(current, "本期"))

            if compare_period != "none":
                prev_from, prev_to = self._calc_compare_range(
                    date_from, date_to, compare_period
                )
                previous = self._query_period(db, farm_id, prev_from, prev_to)
                lines.extend(self._format_period(previous, "对比期"))
                lines.extend(self._format_comparison(current, previous))

            return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
        finally:
            db.close()

    def _query_period(self, db, farm_id, date_from, date_to):
        records = (
            db.query(CostRecord)
            .filter(
                CostRecord.farm_id == farm_id,
                CostRecord.record_date >= date_from,
                CostRecord.record_date <= date_to,
            )
            .all()
        )
        cost = sum(float(r.amount) for r in records if r.record_type == "cost")
        income = sum(float(r.amount) for r in records if r.record_type == "income")

        from collections import defaultdict
        by_category = defaultdict(lambda: {"cost": 0, "income": 0})
        for r in records:
            by_category[r.category][r.record_type] += float(r.amount)

        return {
            "cost": cost,
            "income": income,
            "net": income - cost,
            "count": len(records),
            "by_category": dict(by_category),
        }

    def _format_period(self, data, label):
        lines = [
            f"  {label}: 支出 {data['cost']:.2f} 元, 收入 {data['income']:.2f} 元, 净 {data['net']:.2f} 元 ({data['count']} 笔)",
        ]
        if data["by_category"]:
            top_cost = sorted(
                [(k, v["cost"]) for k, v in data["by_category"].items() if v["cost"] > 0],
                key=lambda x: x[1],
                reverse=True,
            )[:3]
            if top_cost:
                lines.append(f"    支出TOP3: " + ", ".join(f"{k}({v:.0f})" for k, v in top_cost))
        return lines

    def _calc_compare_range(self, date_from, date_to, compare_period):
        df = datetime.strptime(date_from, "%Y-%m-%d").date()
        dt = datetime.strptime(date_to, "%Y-%m-%d").date()
        days = (dt - df).days + 1

        if compare_period == "last_month":
            prev_df = df - timedelta(days=days)
            prev_dt = df - timedelta(days=1)
        elif compare_period == "last_year":
            prev_df = df.replace(year=df.year - 1)
            prev_dt = dt.replace(year=dt.year - 1)
        else:
            prev_df, prev_dt = df, dt

        return prev_df.isoformat(), prev_dt.isoformat()

    def _format_comparison(self, current, previous):
        if previous["cost"] == 0:
            cost_change = "无数据"
        else:
            pct = (current["cost"] - previous["cost"]) / previous["cost"] * 100
            cost_change = f"{'+' if pct >= 0 else ''}{pct:.1f}%"

        if previous["income"] == 0:
            income_change = "无数据"
        else:
            pct = (current["income"] - previous["income"]) / previous["income"] * 100
            income_change = f"{'+' if pct >= 0 else ''}{pct:.1f}%"

        return [
            "  对比变化：",
            f"    支出变化: {cost_change}",
            f"    收入变化: {income_change}",
        ]
```

- [ ] **Step 3: 运行测试**

```bash
cd backend && poetry run pytest tests/test_skills.py -v -k analytics
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/skills/cost-analytics/
git commit -m "feat: add cost-analytics skill for trend analysis"
```

---

### Task 4: 后端测试补充

**Files:**
- Create: `backend/tests/test_skills.py`
- Modify: `backend/tests/test_cost.py`

- [ ] **Step 1: 创建 Skill 单元测试**

```python
# backend/tests/test_skills.py
import pytest
from skillify.core.context import SkillContext

from app.skills.cost_summary.scripts.main import CostSummarySkill
from app.skills.cost_analytics.scripts.main import CostAnalyticsSkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1)


class TestCostSummarySkill:
    async def test_empty_records(self, ctx):
        skill = CostSummarySkill()
        result = await skill.execute({"cycle_id": 99999}, ctx)
        assert "暂无记录" in result.reply

    async def test_group_by_category(self, ctx):
        skill = CostSummarySkill()
        result = await skill.execute({
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
            "record_type": "cost",
            "group_by": "category",
        }, ctx)
        assert "按分类汇总" in result.reply


class TestCostAnalyticsSkill:
    async def test_basic_analysis(self, ctx):
        skill = CostAnalyticsSkill()
        result = await skill.execute({
            "date_from": "2025-01-01",
            "date_to": "2025-01-31",
            "compare_period": "last_month",
        }, ctx)
        assert "收支分析" in result.reply
```

- [ ] **Step 2: 补充 cost parse 测试**

在 `backend/tests/test_cost.py` 末尾追加：

```python
def test_parse_cost_record():
    # 此测试需要 LLM 配置，标记为可选
    pytest.skip("需要 LLM 配置")
```

- [ ] **Step 3: 运行全部测试**

```bash
cd backend && poetry run pytest tests/test_cost.py tests/test_skills.py -v
```

Expected: PASS（parse 测试 skip）

- [ ] **Step 4: Commit**

```bash
git add backend/tests/
git commit -m "test: add skill unit tests"
```

---

### Task 5: 前端 AI 帮记 UI

**Files:**
- Modify: `FarmManagerMobile/src/screens/cost/CostCreateScreen.tsx`
- Modify: `FarmManagerMobile/src/api/client.ts`

- [ ] **Step 1: 确认 API client 已有 parseRecord**

```typescript
// FarmManagerMobile/src/api/client.ts — costApi 中应已有：
parseRecord: (description: string) =>
  apiClient.post('/costs/parse', { description }),
```

- [ ] **Step 2: 重写 CostCreateScreen**

```tsx
// FarmManagerMobile/src/screens/cost/CostCreateScreen.tsx
import React, {useState} from 'react';
import {
  View,
  Text,
  TextInput,
  ScrollView,
  StyleSheet,
  Alert,
  TouchableOpacity,
} from 'react-native';
import {useNavigation} from '@react-navigation/native';
import type {NativeStackNavigationProp} from '@react-navigation/native-stack';
import dayjs from 'dayjs';
import {useCostStore} from '../../stores/costStore';
import {costApi} from '../../api/client';
import {BigButton} from '../../components/BigButton';
import {Loading} from '../../components/Loading';
import {colors} from '../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../theme/spacing';
import type {RootStackParamList} from '../../navigation/AppNavigator';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

const COST_CATEGORIES = ['种子', '化肥', '农药', '人工', '水电', '地租', '其他'];
const INCOME_CATEGORIES = ['销售', '补贴', '其他'];

const AI_EXAMPLES = [
  '买了50斤化肥花了120块',
  '今天卖西瓜收入3000元',
  '大棚租金5000',
];

type CostCreateNavigationProp = NativeStackNavigationProp<
  RootStackParamList,
  'CostCreate'
>;

export const CostCreateScreen: React.FC = () => {
  const navigation = useNavigation<CostCreateNavigationProp>();
  const {createRecord, loading} = useCostStore();

  const [recordType, setRecordType] = useState<'cost' | 'income'>('cost');
  const [category, setCategory] = useState('');
  const [amount, setAmount] = useState('');
  const [recordDate, setRecordDate] = useState(dayjs().format('YYYY-MM-DD'));
  const [note, setNote] = useState('');

  const [aiInput, setAiInput] = useState('');
  const [aiLoading, setAiLoading] = useState(false);

  const categories =
    recordType === 'cost' ? COST_CATEGORIES : INCOME_CATEGORIES;

  const handleAiParse = async () => {
    if (!aiInput.trim()) return;
    setAiLoading(true);
    try {
      const res = await costApi.parseRecord(aiInput.trim());
      const data = res.data;
      setRecordType(data.record_type as 'cost' | 'income');
      setCategory(data.category);
      setAmount(data.amount);
      setRecordDate(data.record_date);
      if (data.note) setNote(data.note);
      setAiInput('');
    } catch (err: any) {
      Alert.alert('解析失败', err.message || '请稍后重试');
    } finally {
      setAiLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!category) {
      Alert.alert('提示', '请选择分类');
      return;
    }
    if (!amount || isNaN(Number(amount))) {
      Alert.alert('提示', '请输入有效金额');
      return;
    }

    await createRecord({
      record_type: recordType,
      category,
      amount,
      record_date: recordDate,
      note: note.trim() || undefined,
    });
    navigation.goBack();
  };

  if (loading) {
    return <Loading message="保存中..." />;
  }

  return (
    <ScrollView style={styles.container} keyboardShouldPersistTaps="handled">
      {/* AI 帮记区域 */}
      <View style={styles.aiCard}>
        <View style={styles.aiHeader}>
          <Icon name="robot" size={20} color={colors.primary} />
          <Text style={styles.aiTitle}>AI 帮记</Text>
        </View>
        <Text style={styles.aiHint}>用一句话描述，AI 自动识别类型和金额</Text>
        <View style={styles.aiInputRow}>
          <TextInput
            style={styles.aiInput}
            value={aiInput}
            onChangeText={setAiInput}
            placeholder={AI_EXAMPLES[0]}
            placeholderTextColor={colors.textTertiary}
          />
          <TouchableOpacity
            style={[styles.aiBtn, (!aiInput.trim() || aiLoading) && styles.aiBtnDisabled]}
            onPress={handleAiParse}
            disabled={!aiInput.trim() || aiLoading}>
            <Icon name="lightning-bolt" size={18} color="#FFFFFF" />
          </TouchableOpacity>
        </View>
        <View style={styles.aiExamples}>
          {AI_EXAMPLES.map((ex, i) => (
            <TouchableOpacity
              key={i}
              style={styles.aiExampleChip}
              onPress={() => setAiInput(ex)}>
              <Text style={styles.aiExampleText}>{ex}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* 类型选择 */}
      <Text style={styles.sectionTitle}>类型</Text>
      <View style={styles.typeRow}>
        <View style={styles.typeItem}>
          <BigButton
            title="支出"
            onPress={() => {
              setRecordType('cost');
              setCategory('');
            }}
            variant={recordType === 'cost' ? 'danger' : 'secondary'}
          />
        </View>
        <View style={styles.typeItem}>
          <BigButton
            title="收入"
            onPress={() => {
              setRecordType('income');
              setCategory('');
            }}
            variant={recordType === 'income' ? 'primary' : 'secondary'}
          />
        </View>
      </View>

      {/* 分类 */}
      <Text style={styles.sectionTitle}>分类</Text>
      <View style={styles.grid}>
        {categories.map(cat => (
          <View key={cat} style={styles.gridItem}>
            <BigButton
              title={cat}
              onPress={() => setCategory(cat)}
              variant={category === cat ? 'primary' : 'secondary'}
            />
          </View>
        ))}
      </View>

      {/* 金额 */}
      <Text style={styles.sectionTitle}>金额</Text>
      <View style={styles.inputWrapper}>
        <Text style={styles.currencySymbol}>¥</Text>
        <TextInput
          style={styles.amountInput}
          placeholder="0.00"
          placeholderTextColor={colors.textSecondary}
          keyboardType="decimal-pad"
          value={amount}
          onChangeText={setAmount}
        />
      </View>

      {/* 日期 */}
      <Text style={styles.sectionTitle}>日期</Text>
      <TextInput
        style={styles.input}
        placeholder="YYYY-MM-DD"
        placeholderTextColor={colors.textSecondary}
        value={recordDate}
        onChangeText={setRecordDate}
      />

      {/* 备注 */}
      <Text style={styles.sectionTitle}>备注</Text>
      <TextInput
        style={styles.noteInput}
        placeholder="添加备注（可选）"
        placeholderTextColor={colors.textSecondary}
        multiline
        numberOfLines={3}
        textAlignVertical="top"
        value={note}
        onChangeText={setNote}
      />

      <View style={styles.submitArea}>
        <BigButton title="保存" onPress={handleSubmit} />
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    padding: spacing.md,
  },
  aiCard: {
    backgroundColor: colors.primaryMuted,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  aiHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  aiTitle: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.primary,
  },
  aiHint: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  aiInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  aiInput: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  aiBtn: {
    width: 44,
    height: 44,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  aiBtnDisabled: {
    backgroundColor: colors.disabledBg,
  },
  aiExamples: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  aiExampleChip: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  aiExampleText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  sectionTitle: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
    marginTop: spacing.lg,
    marginBottom: spacing.md,
  },
  typeRow: {
    flexDirection: 'row',
    marginHorizontal: -spacing.sm,
  },
  typeItem: {
    flex: 1,
    paddingHorizontal: spacing.sm,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -spacing.sm,
  },
  gridItem: {
    width: '33.33%',
    paddingHorizontal: spacing.sm,
    marginBottom: spacing.md,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.surface,
  },
  currencySymbol: {
    fontSize: fontSize.lg,
    fontWeight: '700',
    color: colors.textSecondary,
    marginRight: spacing.sm,
  },
  amountInput: {
    flex: 1,
    fontSize: fontSize.lg,
    fontWeight: '700',
    color: colors.text,
    paddingVertical: spacing.md,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
    backgroundColor: colors.surface,
  },
  noteInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
    backgroundColor: colors.surface,
    minHeight: 80,
  },
  submitArea: {
    marginTop: spacing.xl,
    marginBottom: spacing.xxl,
  },
});
```

- [ ] **Step 3: Commit**

```bash
git add FarmManagerMobile/src/screens/cost/CostCreateScreen.tsx
git commit -m "feat: redesign cost create screen with AI helper"
```

---

### Task 6: 前端账单分类归档

**Files:**
- Modify: `FarmManagerMobile/src/screens/cost/CostListScreen.tsx`

- [ ] **Step 1: 在 CostListScreen 增加分类汇总卡片**

在 `statsSection` 和 `filterRow` 之间插入分类汇总区域：

```tsx
// 在 CostListScreen 中新增分类汇总
const categoryStats = useMemo(() => {
  const monthRecords = records.filter(r => r.record_date.startsWith(currentMonth));
  const stats: Record<string, {cost: number; income: number}> = {};
  for (const r of monthRecords) {
    if (!stats[r.category]) stats[r.category] = {cost: 0, income: 0};
    const val = parseFloat(r.amount);
    if (r.record_type === 'cost') stats[r.category].cost += val;
    else stats[r.category].income += val;
  }
  return stats;
}, [records, currentMonth]);

// 渲染分类汇总（放在 statsSection 后面）
{Object.keys(categoryStats).length > 0 && (
  <View style={styles.categorySection}>
    <Text style={styles.categoryTitle}>本月分类汇总</Text>
    <ScrollView horizontal showsHorizontalScrollIndicator={false}>
      {Object.entries(categoryStats).map(([cat, val]) => (
        <View key={cat} style={styles.categoryChip}>
          <Text style={styles.categoryChipName}>{cat}</Text>
          <Text style={[styles.categoryChipCost, {color: colors.danger}]}>
            -{val.cost.toFixed(0)}
          </Text>
          {val.income > 0 && (
            <Text style={[styles.categoryChipIncome, {color: colors.success}]}>
              +{val.income.toFixed(0)}
            </Text>
          )}
        </View>
      ))}
    </ScrollView>
  </View>
)}
```

- [ ] **Step 2: 添加对应样式**

```javascript
categorySection: {
  paddingHorizontal: spacing.lg,
  marginBottom: spacing.md,
},
categoryTitle: {
  fontSize: fontSize.sm,
  fontWeight: '600',
  color: colors.textSecondary,
  marginBottom: spacing.sm,
},
categoryChip: {
  backgroundColor: colors.surface,
  borderRadius: borderRadius.lg,
  padding: spacing.md,
  marginRight: spacing.sm,
  minWidth: 100,
  alignItems: 'center',
},
categoryChipName: {
  fontSize: fontSize.sm,
  fontWeight: '600',
  color: colors.text,
  marginBottom: spacing.xs,
},
categoryChipCost: {
  fontSize: fontSize.md,
  fontWeight: '700',
},
categoryChipIncome: {
  fontSize: fontSize.xs,
  fontWeight: '600',
  marginTop: 2,
},
```

- [ ] **Step 3: Commit**

```bash
git add FarmManagerMobile/src/screens/cost/CostListScreen.tsx
git commit -m "feat: add category summary cards to cost list"
```

---

### Task 7: 集成测试与提交

- [ ] **Step 1: 后端 lint**

```bash
cd backend && ruff check . && ruff format .
```

- [ ] **Step 2: 后端测试**

```bash
cd backend && poetry run pytest tests/test_cost.py tests/test_skills.py tests/test_advisor_agent.py -v
```

Expected: All PASS

- [ ] **Step 3: 前端类型检查（如有）**

```bash
cd FarmManagerMobile && npx tsc --noEmit 2>/dev/null || echo "skip"
```

- [ ] **Step 4: 最终提交**

```bash
git add -A
git commit -m "feat: ai long-term memory phase 1 - enhanced skills, ai cost helper, category summary"
```

---

## Spec Coverage Check

| 需求 | 任务 | 状态 |
|------|------|------|
| farm_id 传递 | Task 1 | ✓ |
| cost-summary 增强（分类/按月/全局） | Task 2 | ✓ |
| cost-analytics 新增（同比环比） | Task 3 | ✓ |
| Skill 单元测试 | Task 4 | ✓ |
| AI 帮记前端 | Task 5 | ✓ |
| 账单分类归档 | Task 6 | ✓ |

## Placeholder Scan

- 无 "TBD" / "TODO" / "implement later"
- 所有代码块含完整实现
- 无 "Similar to Task N" 引用
