"""Tool 选择规则配置。"""

from __future__ import annotations

import re

WRITE_INTENT_HINTS = {"创建", "新建", "记录", "记下", "添加"}
QUERY_INTENT_HINTS = {"查询", "查看", "最近", "有哪些", "多少", "还欠", "统计"}

WRITE_PATTERNS: dict[str, list[re.Pattern]] = {
    "create_cost_record": [
        re.compile(r"(?:买了|卖了|花了|收入|支出|赊账|记账|记一笔|付了|收了)"),
        re.compile(r"\d+\s*(?:元|块|万|w|W|千|百)"),
    ],
    "settle_debt": [
        re.compile(r"(?:还[了钱账给]|清账|还款)"),
        re.compile(r"还(?!欠).{1,20}\d+\s*(?:元|块|万|w|W|千|百)?"),
        re.compile(r"(?:账[结清]|结了.*账|欠.*结)"),
    ],
    "delete_cost_record": [
        re.compile(r"(?:删除|撤销|删掉|移除).*(?:账务|账单|流水|收支|成本|收入|费用)"),
        re.compile(
            r"(?:账务|账单|流水|收支|成本|收入|费用).*#?\d+.*(?:删除|撤销|删掉|移除)"
        ),
    ],
    "manage_cost_categories": [
        re.compile(r"(?:新增|添加|创建|新建).*(?:成本|收入|账务|费用).{0,6}分类"),
        re.compile(r"(?:删除|删掉|移除).*(?:成本|收入|账务|费用).{0,6}分类"),
        re.compile(r"(?:分类).*(?:新增|添加|创建|新建|删除|删掉|移除)"),
    ],
    "create_crop_cycle": [
        re.compile(r"(?:创建|建|开)\s*.*茬口"),
        re.compile(r"(?:种植|种[了上下]?)\s*(?:西瓜|番茄|辣椒|豆角|黄瓜|玉米)"),
        re.compile(r"(?:我想|我要|想要|准备|打算)\s*种\s*[\u4e00-\u9fa5]{1,12}$"),
        re.compile(r"(?:春茬|秋茬|夏茬|冬茬)"),
    ],
    "create_crop_template": [
        re.compile(r"(?:创建|建|新建|添加).*(?:作物|模板)"),
        re.compile(r"(?:没有|缺少|找不到).*(?:模板|作物)"),
    ],
    "manage_crop_templates": [
        re.compile(r"(?:修改|更改|调整|更新|改|删除|删掉|移除).*(?:作物模板|模板)"),
        re.compile(
            r"(?:作物模板|模板).*#?\d+.*(?:修改|更改|调整|更新|改|删除|删掉|移除)"
        ),
    ],
    "delete_crop_cycle": [
        re.compile(r"(?:删除|删掉|移除).*(?:茬口|种植周期|批次)"),
        re.compile(r"(?:茬口|种植周期|批次).*#?\d+.*(?:删除|删掉|移除)"),
    ],
    "log_farm_activity": [
        re.compile(r"(?:浇[了水]|施[了肥]|打[了药]|除[了草]|翻[了地]|播[了种])"),
        re.compile(r"(?:记录|记下)\s*(?:农事|操作|浇水|施肥)"),
    ],
    "manage_farm_logs": [
        re.compile(
            r"(?:修改|更改|调整|更新|更正|删除|删掉|移除).*(?:农事记录|农事日志|操作日志|操作记录)"
        ),
        re.compile(
            r"(?:农事记录|农事日志|操作日志|操作记录).*#?\d+.*(?:修改|更改|调整|更新|更正|删除|删掉|移除)"
        ),
    ],
    "update_crop_stage": [
        re.compile(r"(?:进[了入]?).*(?:期|阶段)"),
        re.compile(r"(?:到[了]?|进入)\s*(?:苗期|开花期|结果期|采收期|伸蔓期|定植期)"),
    ],
    "update_crop_cycle": [
        re.compile(r"(?:修改|更改|调整|改|改成|改到).*(?:茬口|周期|开始|播种期|起始)"),
        re.compile(
            r"(?:西瓜|番茄|辣椒|豆角|黄瓜|玉米|水稻).*(?:修改|更改|调整|改|改成|改到).*(?:\d{1,2}月|开始|播种期|起始)"
        ),
    ],
    "create_operation_work_order": [
        re.compile(
            r"(?:安排|派|叫|让).{1,20}(?:去|到).{0,20}(?:授粉|压蔓|留瓜|垫瓜|采收|装车|打杈|绑蔓|整枝)"
        ),
        re.compile(
            r"(?:授粉|压蔓|留瓜|垫瓜|采收|装车|打杈|绑蔓|整枝).*(?:工人|每人|人工|作业|干活)"
        ),
        re.compile(r"(?:创建|新建|记录).*(?:作业单|农事作业|用工)"),
        re.compile(
            r"(?:东大棚|西大棚|地块|棚).*(?:工人|每人|人工).*(?:\d+\s*(?:元|块|人))"
        ),
    ],
    "settle_labor_payment": [
        re.compile(r"(?:补付|支付|结算|付清|结清).*(?:人工|工钱|工资)"),
        re.compile(r"(?:人工|工钱|工资).*(?:补付|支付|结算|付清|结清)"),
        re.compile(r"(?:给|付给).{1,12}(?:\d+\s*(?:元|块|百|千)).*(?:人工|工钱|工资)"),
    ],
    "update_operation_work_order": [
        re.compile(
            r"(?:刚才|上一条|那条|这条).*(?:不是|改成|改为|改到|更正|纠正).*(?:作业|记录|授粉|人工|工人|付)"
        ),
        re.compile(r"(?:修改|更改|调整|纠正).*(?:作业单|农事作业|用工记录)"),
    ],
    "manage_planting_units": [
        re.compile(
            r"(?:新增|添加|创建|新建|修改|更改|调整|更新|删除|删掉|移除).*(?:种植单元|地块|大棚|棚区|棚)"
        ),
        re.compile(
            r"(?:种植单元|地块|大棚|棚区|棚).*#?\d+.*(?:修改|更改|调整|更新|删除|删掉|移除)"
        ),
    ],
    "manage_wages": [
        re.compile(r"(?:记|记录|新增|添加).*(?:工资记录|工资|工钱|人工费)"),
        re.compile(
            r"(?:修改|更改|调整|更新|改).*(?:工资记录|工资单|工钱记录|人工费记录).*(?:\d+\s*(?:元|块|百|千))"
        ),
        re.compile(
            r"(?:工资记录|工资单|工钱记录|人工费记录).*(?:修改|更改|调整|更新|改成|改到)"
        ),
        re.compile(
            r"(?:采收|装车|整枝|打杈|授粉|除草|施肥|浇水).*(?:工资|工钱).*(?:\d+\s*(?:元|块|百|千))"
        ),
    ],
    "manage_workers": [
        re.compile(
            r"(?:新来|来了|入职|刚来|刚招).*(?:工人|员工|师傅).*(?:工资|日薪|时薪|计件|薪资)?\s*\d+\s*(?:元|块)?(?:一?天|/天|每天)?"
        ),
        re.compile(
            r"(?:招(?:了|来)?|招聘|新增|添加|创建|新建).*(?:工人档案|员工档案|工人|员工)"
        ),
        re.compile(
            r"(?:修改|更改|调整|更新).*(?:工人|员工).*(?:工资|日薪|电话|手机号|备注|状态)"
        ),
        re.compile(
            r"(?:[\u4e00-\u9fa5]{2,8}).*(?:工资|日薪|时薪|计件).*(?:更新|改成|改到|调整为).*\d+\s*(?:元|块)?(?:一?天|/天|每天)?"
        ),
        re.compile(r"(?:删除|停用).*(?:工人|员工|师傅|李四|王五|赵六|张三|老王|老李)"),
        re.compile(
            r"(?:工人|员工|师傅|李四|王五|赵六|张三|老王|老李).*(?:离职了|不用了|不要了)"
        ),
        re.compile(r"[\u4e00-\u9fa5]{2,8}(?:离职了|不用了|不要了)"),
        re.compile(
            r"(?:恢复|重新启用|又回来了).*(?:工人|员工|师傅|李四|王五|赵六|张三|老王|老李)"
        ),
    ],
    "manage_user_settings": [
        re.compile(
            r"(?:修改|更改|调整|更新|改).*(?:用户设置|我的设置|默认城市|天气城市|显示名|昵称)"
        ),
        re.compile(
            r"(?:默认城市|天气城市|显示名|昵称).*(?:改成|改为|改到|设置为|更新为)"
        ),
    ],
}

QUERY_TRIGGERS: dict[str, set[str]] = {
    "get_weather_forecast": {"天气", "预报", "降雨", "温度", "极端天气"},
    "get_cost_summary": {
        "余额",
        "收支",
        "成本",
        "利润",
        "花了多少",
        "赚了多少",
        "账单",
        "周账单",
        "月账单",
        "年账单",
        "本周",
        "本月",
        "今年",
        "去年",
        "流水",
        "明细",
        "分类汇总",
        "月额",
    },
    "get_debt_summary": {
        "欠款",
        "赊账",
        "还欠",
        "欠谁",
        "欠别人",
        "我欠别人",
        "我还欠",
        "欠多少钱",
        "欠款统计",
        "赊账统计",
        "欠款汇总",
        "赊账汇总",
    },
    "get_cost_analytics": {"趋势", "对比", "比去年", "比上月", "收支分析"},
    "get_cost_categories": {
        "账务分类",
        "成本分类",
        "收入分类",
        "费用分类",
        "有哪些分类",
    },
    "get_crop_templates": {"作物模板", "模板列表", "有哪些模板", "生长阶段模板"},
    "get_crop_cycle_info": {"茬口", "当前阶段", "周期进度", "阶段"},
    "get_recent_farm_logs": {"农事记录", "操作日志", "干了啥", "记录"},
    "get_planting_units": {"种植单元", "地块", "大棚", "棚区", "有哪些棚"},
    "get_labor_payables": {
        "人工钱",
        "工钱",
        "工资",
        "未付人工",
        "欠人工",
        "还欠多少人工",
        "人工欠款",
    },
    "get_workers": {
        "我的工人",
        "当前工人",
        "活跃工人",
        "工人列表",
        "有哪些工人",
        "离职工人",
        "停用工人",
        "历史工人",
    },
    "get_operation_work_orders": {
        "作业单",
        "农事作业",
        "授粉作业",
        "作业有哪些",
        "用工记录",
        "最近授粉",
        "最近采收",
    },
    "get_farm_status": {"农场", "茬口状态", "种植情况", "农事", "综合状态", "整体情况"},
    "get_user_settings": {
        "用户设置",
        "我的设置",
        "默认城市",
        "天气城市",
        "显示名",
        "昵称",
    },
    "web_search": {
        "最新",
        "新闻",
        "价格",
        "上市",
        "政策",
        "热点",
        "搜索",
        "查一下",
        "最近",
        "实时",
        "网上",
        "网上说",
    },
}

PLANTING_ADVICE_HINTS = (
    "怎么",
    "如何",
    "注意",
    "建议",
    "技术",
    "方法",
    "适合",
    "可以吗",
    "能不能",
    "什么时候",
)

DISABLED_SKILLS: set[str] = {
    "web_search",
}

TOOL_CHAIN_MAP: dict[str, list[str]] = {
    "get_weather_forecast": ["get_farm_status"],
    "get_cost_summary": ["get_farm_status"],
    "get_debt_summary": ["get_farm_status"],
    "get_cost_analytics": ["get_farm_status"],
    "get_crop_cycle_info": ["get_farm_status"],
    "get_recent_farm_logs": ["get_farm_status"],
    "get_labor_payables": ["get_farm_status"],
    "get_workers": ["get_farm_status"],
    "get_operation_work_orders": ["get_farm_status"],
    "get_cost_categories": ["get_farm_status"],
    "get_planting_units": ["get_farm_status"],
    "get_crop_templates": ["get_farm_status"],
    "get_user_settings": ["get_farm_status"],
    "create_cost_record": [],
    "delete_cost_record": [],
    "create_crop_cycle": [],
    "delete_crop_cycle": [],
    "create_crop_template": [],
    "manage_crop_templates": [],
    "create_operation_work_order": [],
    "log_farm_activity": [],
    "manage_farm_logs": [],
    "settle_debt": [],
    "settle_labor_payment": [],
    "update_crop_cycle": [],
    "update_crop_stage": [],
    "update_operation_work_order": [],
    "manage_workers": [],
    "manage_wages": [],
    "manage_cost_categories": [],
    "manage_planting_units": [],
    "manage_user_settings": [],
    "get_farm_status": [],
    "web_search": [],
}
