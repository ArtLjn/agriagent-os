---
last_updated: 2026-05-24
status: active
---

# 模块边界与依赖规则

## 后端依赖矩阵

| 层 | 可依赖 | 不可依赖 |
|---|--------|---------|
| schemas/ | 无 | agents/, api/, core/, models/, services/ |
| agents/ | core/, models/, services/ | api/, schemas/ |
| api/ | core/, models/, schemas/, services/ | agents/ |
| core/ | models/ | agents/, api/, schemas/, services/ |
| models/ | core/ | agents/, api/, schemas/, services/ |
| services/ | agents/, models/, schemas/ | api/, core/ |

## 后端违规示例

```python
# ❌ services/ 层直接 import api/
from app.api.xxx import XxxClass  # 错误！

# ✅ services/ 层通过 agents/ 访问
from app.agents.xxx import XxxService  # 正确
```


## 前端依赖矩阵

| 层 | 可依赖 | 不可依赖 |
|---|--------|---------|
| api/ | 无 | components/, layouts/, pages/ |
| components/ | api/ | layouts/, pages/ |
| layouts/ | 无 | api/, components/, pages/ |
| pages/ | api/, components/ | layouts/ |

## 前端违规示例

```typescript
// ❌ 组件直接调用 services/
import { xxxService } from '@/services/xxx';  // 错误！

// ✅ 组件通过 props 接收数据，页面层调用 services/
<XxxComponent data={data} />  // 正确，数据从页面 props 传入
```

## 豁免机制

特殊情况下需绕过约束时，必须添加注释说明原因：

```python
# harness-exempt: 此处需要直接访问低层，原因见 #PR-XXX
from app.xxx import XxxClass
```
