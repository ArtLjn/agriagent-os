# log-farm-activity

## 类型
写操作(write)

## 触发场景
- 用户说"今天浇了水施了肥"
- 用户说"给西瓜追肥了"
- 用户提到做了什么农活、浇了水、施了肥、打药时

## 参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| operation_type | string | 是 | 农事操作类型，如'浇水'、'施肥'、'打药' |
| operation_date | string | 否 | 操作日期 YYYY-MM-DD，默认今天 |
| note | string | 否 | 备注详情 |
| cycle_id | integer | 否 | 关联茬口ID，不传则自动关联第一个活跃茬口 |

## 返回
成功：「已记录：浇水（2026-05-26，关联西瓜茬口）」

## 依赖
- `services/log_service.py` — create_log
- `models/cycle.py` — CropCycle（自动关联茬口）

## 错误处理
| 场景 | 返回 |
|------|------|
| 缺少操作类型 | FAILED + "请告诉我做了什么" |
| 无活跃茬口 | NEED_CLARIFY + "请先创建一个茬口" |

## 示例对话
用户：「今天浇了水」
Agent → 调用 log_farm_activity(operation_type="浇水")
返回：「已记录：浇水（2026-05-26，关联西瓜茬口）」
