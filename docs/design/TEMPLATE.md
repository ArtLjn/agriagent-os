---
last_updated: 2026-05-24
status: draft          # draft | approved | in_progress | implemented | deprecated
---

# Feature: [功能名称]

## 目标
一句话描述这个功能要解决什么问题。

## 非目标
明确列出这次**不做什么**（防止 Agent 扩大范围）：
- 不做 XXX
- 不做 XXX

## 技术方案

### 涉及的模块
- models/: 新增/修改 XXX
- repositories/: 新增/修改 XXX
- services/: 新增/修改 XXX
- api/: 新增/修改 XXX

### 数据模型变更
```sql
-- 如有数据库变更，写在这里
```

### API 变更
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/v1/xxx | ... |

请求/响应体：
```json
{ "request": "...", "response": "..." }
```

## 验收标准
- [ ] 标准1：具体的、可验证的
- [ ] 标准2：具体的、可验证的
- [ ] 测试覆盖率 ≥ 80%

## 依赖
- 依赖 feature-xxx（状态：✅ 已实现 / 📋 已审批 / 🚧 开发中）
