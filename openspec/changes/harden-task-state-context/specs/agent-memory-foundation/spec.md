## MODIFIED Requirements

### Requirement: Session Summary 触发参数

`session_summary_message_threshold` 默认值从 12 调整为 8。`session_summary_debounce_minutes` 默认值从 30 调整为 10。依据:`backend/scripts/context_multiturn_spike.py` `recent_messages_truncation` scenario 实证——threshold=12 时 turn 9-10 存在 recent 已截断但 summary 未触发的失忆窗口,threshold=8 可消除。

#### Scenario: 第 8 条消息触发 summary

- **WHEN** 会话累计 8 条 messages(user+assistant)且距上次 summary > 10 分钟
- **THEN** MemoryService.maybe_summarize 实际调 `generate_summary`,成功则更新 conversation.summary

#### Scenario: 10 分钟内不重复触发

- **WHEN** 会话累计 12 条 messages,但距上次 summary 仅 5 分钟
- **THEN** maybe_summarize 走 `within_debounce_window` 分支跳过,trace 记录 reason
