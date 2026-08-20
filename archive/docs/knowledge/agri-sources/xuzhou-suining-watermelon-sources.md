# 睢宁设施西瓜知识源审查表

采集日期：2026-07-23  
服务基准：江苏徐州睢宁，优先魏集镇设施西瓜、春提早、大棚/多层覆盖。

## 本轮结论

这轮不追求数量，只保留能服务具体问题的资料。核心本地资料 2 条，徐州防寒风险资料 1 条，江苏/长三角 fallback 2 条，气候入口 1 条。

| ID | 标题 | 地区 | 主题 | 等级 | 入库策略 | 知识卡 |
| --- | --- | --- | --- | --- | --- | --- |
| sn-watermelon-001 | [徐州睢宁县魏集镇：西瓜“三本经”助农“甜蜜收”](https://jsnews.jschina.com.cn/xz/a/202502/t20250220_s67b6c298e4b05777c1785468.shtml) | 徐州/睢宁/魏集镇 | 栽培管理 | B | 核心 RAG + 农时候选 | `sn-watermelon-001-weiji-management.md` |
| sn-watermelon-002 | [睢宁魏集西瓜持续25年走俏市场的秘诀](https://jsnews.jschina.com.cn/xz/a/202005/t20200521_2555607.shtml) | 徐州/睢宁/魏集镇 | 案例/日程 | B | 核心 RAG + 农时候选 | `sn-watermelon-002-weiji-industry-calendar.md` |
| sn-watermelon-003 | [江苏徐州：从“人防”到“技防”，农作物防寒尽显科技范儿](https://www.xhby.net/content/s65c5c159e4b0cb6e600e7dca.html) | 徐州 | 风险 | B | 徐州风险 RAG | `sn-watermelon-003-xuzhou-cold-risk.md` |
| sn-watermelon-004 | [亚夫科技服务护航春提早蔬菜定植生产](https://www.jaas.ac.cn/xww/kjfw/art/2026/art_baefae7e12eb46609c41c1fea21bc3b3.html) | 江苏/南京 | 定植 | A | 江苏 fallback | `sn-watermelon-004-jiangsu-transplant-fallback.md` |
| sn-watermelon-005 | [西瓜甜瓜设施栽培水肥一体化技术](https://nyncw.sh.gov.cn/nyjs/20181129/0009-107593.html) | 上海 | 肥水 | A | 设施肥水 fallback | `sn-watermelon-005-fertigation-fallback.md` |
| sn-watermelon-006 | [WMO 徐州气候资料](https://worldweather.wmo.int/zh/city.html?cityId=1864) | 徐州 | 气候 | S | 仅 source index，后续结构化 | 无 |

## 可抽取事实

- 魏集镇设施西瓜在 2 月低温下已有抽蔓期管理场景。
- 魏集本地报道给出白天约 25℃、夜间 10℃以上的棚温管理口径。
- 2025 年报道给出每亩最多约 900 棵；2020 年报道给出每亩限制约 550 棵，需按品种、棚型、年份保留差异。
- 魏集本地有“上一年 11 月或 12 月开始育苗栽植”的报道，应继续用农技规程或一线访谈校验。
- 魏集本地上市窗口有 4 月初、4 月中下旬两个口径，需按品种、覆盖层数和抢早程度区分。
- 徐州 2 月强寒潮雨雪是设施农业风险场景，应纳入倒春寒/雨雪防灾知识。
- 江苏农科院报道可作为 3 月中旬春提早西瓜定植管理 fallback。
- 上海水肥一体化资料可作为设施西瓜膨瓜肥水 fallback，不直接等同于睢宁。

## 仍缺资料

- 睢宁县农业农村局或徐州市农业农村局正式发布的设施西瓜技术规程。
- 睢宁魏集镇实际育苗、定植、授粉、上市的年度记录。
- 徐州/睢宁近 10 年 2-4 月温度、降水、倒春寒统计。
- 睢宁设施西瓜常见病害的本地发生期和防治口径。
- 8424、京欣、嘉年华、美都、苏蜜系列在睢宁的品种表现资料。
