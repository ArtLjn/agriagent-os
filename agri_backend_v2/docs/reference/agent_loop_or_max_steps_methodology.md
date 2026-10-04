# Agent Harness Runtime Control 方法论

## 1. 背景

在 Agent 系统中，LLM 本身并不能保证任务执行一定收敛。

典型问题：

* 无限重复调用相同 Tool
* Tool 返回结果后无法推进任务
* Agent 在多个相似 Action 之间震荡
* 复杂任务因为固定 max_steps 提前终止
* 简单任务浪费大量执行预算

因此 Agent Runtime 需要增加控制层：

```
                User Request

                     |
                     v

              Task Planner

                     |
        +------------+-------------+
        |                          |
        v                          v

   Execution Plan           Step Budget

        |
        v

          Agent Runtime Loop

        Thought
          |
        Action
          |
        Tool
          |
     Observation
          |
     State Update
          |
  Progress Evaluation
          |
   Loop Detection
          |
      Continue?


```

---

# 2. 核心思想

## Agent 不应该是：

```
while steps < max_steps:

    LLM decide next action

    execute tool

```

这种模式的问题：

* LLM 每轮重新决策
* 没有任务状态
* 不知道完成了什么
* 容易重复

---

## 推荐模式：

```
Planner

生成：

Goal

↓

Plan

↓

Execution State


Runtime

根据 State 推进任务

```

即：

> LLM 负责推理，Runtime 负责控制。

---

# 3. Execution State 设计

Agent Runtime 必须维护执行状态。

推荐：

```json
{
  "goal": "帮助用户规划20亩虎丘水稻种植方案",

  "phase": "information_collection",

  "plan": [
    {
      "step":1,
      "task":"获取水稻模板",
      "status":"completed"
    },
    {
      "step":2,
      "task":"获取虎丘环境信息",
      "status":"pending"
    },
    {
      "step":3,
      "task":"计算投入产出",
      "status":"pending"
    }
  ],

  "completed_actions":[
      "list_system_crop_templates"
  ],

  "last_progress_time":
      "2026-08-27T15:00:00"

}
```

---

## State 的作用

每次 Tool 执行后：

不要只返回：

```
Tool Result
```

而应该：

```
Tool Result

        +

State Update

```

例如：

Tool:

```
list_system_crop_templates()
```

返回：

```
水稻模板
```

Runtime 更新：

```json
{
 "step1":
 {
   "status":"completed"
 }
}
```

下一轮 Agent 才知道：

```
模板已经获取

下一步应该查询气候

```

---

# 4. Doom Loop Detection 方法论

## 4.1 为什么需要 Doom Loop

LLM Agent 最大风险：

```
Action -> Observation -> Action

无限循环

```

例如：

```
list_system_crop_templates()

↓

返回模板

↓

list_system_crop_templates()

↓

返回模板

```

---

# 5. Loop Detection 分层设计

不要只检测：

```
tool name + args

```

应该分三层。

---

# Level 1：Exact Action Loop

## 定义

完全相同 Action 重复。

例如：

```
Tool:
list_system_crop_templates

Args:
{}

```

连续：

```
3次

```

触发。

规则：

```
same_tool
+
same_arguments
+
repeat >=3

=> block

```

---

# Level 2：Semantic Action Loop

问题：

不同 Tool 可能完成同一个目的。

例如：

```
list_system_crop_templates

query_crop_templates

```

虽然名字不同：

但是语义：

```
查询种植模板

```

属于同一个 Action Group。

设计：

建立 Tool Capability Group。

例如：

```json
{
 "crop_template_query":[

   "list_system_crop_templates",

   "query_crop_templates",

   "search_crop_templates"

 ]
}
```

检测：

```
same capability group

repeat >=3

```

触发。

---

# Level 3：No Progress Loop

这是最重要的一层。

判断：

Agent 是否产生状态变化。

例如：

连续：

```
Action:

query_template


State:

没有变化

```

说明：

Agent 没有推进。

检测：

```json
{
 "before_state_hash":
 "abc",

 "after_state_hash":
 "abc"
}
```

连续：

```
3次无变化

```

终止。

---

# 6. Doom Loop 处理策略

不要直接：

```
terminate

```

应该：

## 第一次

提醒 Agent：

```
检测到重复查询。

已有结果，请基于已有信息继续下一阶段。

```

---

## 第二次

强制切换：

```
进入 Recovery Mode

```

例如：

给 LLM 增加：

```
Previous actions failed.

Choose another strategy.

```

---

## 第三次

终止：

```
无法继续推进

```

---

推荐：

```
Warning

↓

Recovery

↓

Terminate

```

---

# 7. Dynamic Max Steps 方法论

## 7.1 固定 max_steps 的问题

例如：

```python
max_steps=10
```

问题：

简单任务：

```
天气查询

实际:
2 steps

浪费

```

复杂任务：

```
经营规划

需要:
20 steps

提前结束

```

---

# 8. Planner Based Step Budget

流程：

```
User Request

        |

        v

Task Planner

        |

        v

Estimated Complexity

        |

        v

Runtime Budget

```

Planner 输出：

```json
{
 "complexity":"medium",

 "estimated_steps":8,

 "confidence":0.8
}
```

---

Runtime:

计算：

```
budget =
estimated_steps * safety_factor

```

例如：

```
8 * 1.5

=

12 steps

```

---

# 9. Budget Clamp

不能完全相信 LLM。

使用：

```
final_steps =
min(
 max(
  estimated_steps * factor,
  minimum
 ),
 maximum
)

```

例如：

```python
final_steps = min(
    max(
        estimate * 1.5,
        5
    ),
    30
)
```

结果：

| 任务   | 估算 | 最终 |
| ---- | -- | -- |
| 查询天气 | 2  | 5  |
| 生成方案 | 8  | 12 |
| 复杂分析 | 20 | 30 |

---

# 10. Step Budget 与 Loop Detection 联动

两个控制职责不同。

## max_steps

解决：

```
正常任务太长

```

## loop detection

解决：

```
异常不收敛

```

关系：

```
          Agent Runtime

               |

       +---------------+

       |               |

 Step Budget      Loop Detector


       |               |

 最大执行次数       异常终止


```

---

# 11. Runtime Control 推荐架构

最终：

```
Agent Harness Runtime


├── Planner
│
│   ├── Goal Extraction
│   ├── Task Decomposition
│   └── Step Estimation
│
│
├── Execution State
│
│   ├── Current Goal
│   ├── Current Phase
│   ├── Completed Steps
│   └── Pending Steps
│
│
├── Budget Controller
│
│   ├── Dynamic max_steps
│   ├── Timeout
│   └── Token Budget
│
│
├── Progress Tracker
│
│   ├── State Diff
│   └── Completion Detection
│
│
└── Loop Controller
    |
    ├── Exact Loop
    ├── Semantic Loop
    └── No Progress Loop

```

---

# 12. 针对当前农业 Agent 案例改造

当前：

```
用户:
20亩虎丘水稻规划


Agent:

查询水稻模板

查询水稻模板

查询水稻模板


doom_loop
```

---

改造后：

```
Planner:

Goal:
生成20亩虎丘水稻方案


Plan:

1.
获取水稻模板

2.
获取地区信息

3.
计算成本

4.
生成方案


Budget:

12 steps


Runtime:

Step1:

list_system_crop_templates

State:

step1 completed


Step2:

get_weather


Step3:

calculate_profit


Step4:

generate_plan


Finish

```

---

# 13. 最终设计原则

## Principle 1

> LLM 决策，Runtime 控制。

---

## Principle 2

> Tool Result 必须改变 Agent State。

---

## Principle 3

> max_steps 是预算，不是控制 Agent 的唯一手段。

---

## Principle 4

> Doom Loop 检测应该检测“不推进”，而不是只检测“重复调用”。

---

## Principle 5

> 复杂 Agent 的稳定性来自 State Machine，而不是 Prompt。

---

这部分应该归入你之前 Harness 方法论里的 **Runtime Control 章节**，和 Context、Router、SSE 属于同一级设计模块。你现在遇到的 doom_loop，本质上说明 Runtime 层还缺少 **Execution State + Progress Controller**。
