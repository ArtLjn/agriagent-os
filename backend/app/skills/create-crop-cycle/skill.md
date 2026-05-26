# create-crop-cycle

## 类型
写操作(write)

## 触发场景
- 用户说"帮我建个秋季辣椒茬口"
- 用户说"我要开始种西瓜"
- 用户提到建茬口、种什么、开始种某作物时

## 参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| crop_name | string | 是 | 作物名称，如'辣椒'、'西瓜' |
| season | string | 否 | 季节，如'春季'、'秋季'，默认当前季节 |
| start_date | string | 否 | 开始日期 YYYY-MM-DD，默认今天 |
| field_name | string | 否 | 地块名称 |

## 返回
成功：「已建茬口：秋季辣椒，共5个阶段：播种期→苗期→…」

## 依赖
- `services/cycle_service.py` — create_crop_cycle
- `services/crop_service.py` — find_template_by_name

## 错误处理
| 场景 | 返回 |
|------|------|
| 缺少作物名 | FAILED + "请告诉我种什么" |
| 无匹配模板 | FAILED + "系统还没有{crop_name}模板..." |

## 示例对话
用户：「帮我建个秋季辣椒茬口」
Agent → 调用 create_crop_cycle(crop_name="辣椒", season="秋季")
返回：「已建茬口：秋季辣椒，共5个阶段」
