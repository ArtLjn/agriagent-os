# create-cost-record

## 类型
写操作(write)

## 触发场景
- 用户说"昨天买了200块化肥"
- 用户说"在农资店老王那赊了3000块大棚膜"
- 用户提到花了钱、买了东西、卖了东西、有收入/支出时

## 参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| amount | number | 是 | 金额，必须大于0 |
| category | string | 是 | 分类，如'化肥'、'人工'、'大棚膜' |
| record_date | string | 否 | 记录日期 YYYY-MM-DD，默认今天 |
| record_type | string | 否 | cost(支出)或income(收入)，默认cost |
| note | string | 否 | 备注，如'赊账-农资店老王' |

## 返回
成功：「已记账：化肥 200元（现金），日期 2026-05-26」

## 依赖
- `services/cost_service.py` — create_record
- `schemas/cost.py` — CostRecordCreate

## 错误处理
| 场景 | 返回 |
|------|------|
| 缺少金额 | FAILED + "请告诉我花了多少钱" |
| 缺少分类 | FAILED + "请告诉我买了什么" |
| 金额无效 | FAILED + "金额必须大于0" |

## 示例对话
用户：「昨天买了200块化肥」
Agent → 调用 create_cost_record(amount=200, category="化肥", record_date="2026-05-25")
返回：「已记账：化肥 200元（现金），日期 2026-05-25」
