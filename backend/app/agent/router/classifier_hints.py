"""RuleIntentClassifier 使用的中文触发词常量。"""

QUERY_HINTS = ("哪些", "有哪些", "看看", "查询", "查一下", "最近", "怎么样", "列表")
FARM_HINTS = ("作物", "栽种", "农场", "茬口", "种植")
CROP_HINTS = ("作物", "栽种", "茬口", "种植")
DAILY_ADVICE_TIME_HINTS = ("今天", "明天", "这几天", "最近")
DAILY_ADVICE_ACTION_HINTS = ("适合", "该做", "做什么", "做啥", "安排什么", "干什么", "干啥")
WEATHER_SENSITIVE_OPERATION_HINTS = ("打药", "施药", "喷药", "浇水", "施肥", "采收", "播种", "移栽")
WRITE_ACTION_HINTS = ("处理", "弄一下", "搞一下", "删", "删除", "改", "修改", "停用", "禁用")
WRITE_ENTITY_HINTS = ("工人", "作业", "账", "分类", "种植单元", "地块", "大棚", "棚区", "号棚")
WORKER_CREATE_HINTS = ("新来", "招了", "新增", "创建", "添加")
WORKER_UPDATE_HINTS = ("改", "修改", "更新", "设置", "设为")
WORKER_DEACTIVATE_HINTS = ("删除", "删掉", "删", "停用", "离职", "不用了")
WORKER_RESTORE_HINTS = ("恢复", "回来", "回来了", "返岗")
WORKER_UPDATE_FIELDS = ("电话", "手机号", "手机", "工资", "日薪", "单价", "备注", "姓名", "名字", "状态")
WORKER_PAY_HINTS = ("工资", "日薪", "每天", "一天")
WORK_ORDER_HINTS = ("作业", "采收", "授粉", "安排")
OPERATION_HINTS = ("授粉", "装车", "整枝", "打杈", "压蔓", "压瓜", "留瓜", "垫瓜")
WORK_ORDER_READ_HINTS = ("作业单", "作业", "采收", "授粉")
READ_BLOCKERS = ("哪些", "有哪些", "查询", "查一下", "看看", "最近", "我的")
PLANTING_ADVICE_HINTS = ("怎么种", "如何种", "咋种", "要注意什么")
WEB_SEARCH_HINTS = ("搜索", "网上查", "新闻")
WEATHER_HINTS = ("天气", "预报", "降雨", "下雨", "气温", "风力", "湿度", "极端天气")
FINANCE_OVERVIEW_HINTS = ("money", "finance", "financial")
COST_SUMMARY_HINTS = (
    "余额",
    "收支",
    "成本",
    "利润",
    "账单",
    "流水",
    "花了多少",
    "赚了多少",
    "收入多少",
    "支出多少",
)
COST_RECORD_WRITE_HINTS = ("买", "采购", "购入", "花了", "支出", "记一笔", "记录")
COST_RECORD_ENTITIES = ("化肥", "肥料", "种子", "农药", "农资", "成本", "费用", "支出")
DEBT_SUMMARY_HINTS = ("还欠", "欠款", "欠多少钱", "欠别人多少钱", "赊账统计", "赊账还欠", "总欠款")
COST_ANALYTICS_HINTS = ("趋势", "同比", "环比", "比上个月", "比去年", "分析")
DELETE_COST_HINTS = ("删除账务", "删除账单", "删除流水", "撤销账单", "撤销账务")
SETTLE_DEBT_HINTS = ("还钱", "还账", "还款", "清账", "结清", "全还")
LABOR_PAYABLE_HINTS = ("人工钱", "工钱", "工资", "未付人工", "欠人工", "还欠多少人工", "人工欠款")
LABOR_SETTLE_HINTS = ("补付", "支付", "结算", "付清", "结清", "结了")
WAGE_RECORD_HINTS = ("记", "记录", "新增", "添加", "修改", "更改", "调整", "更新")
COST_CATEGORY_HINTS = ("账务分类", "成本分类", "收入分类", "费用分类", "有哪些分类", "查询分类")
COST_CATEGORY_ENTITY_HINTS = ("账务分类", "成本分类", "收入分类", "费用分类", "支出分类", "分类")
COST_CATEGORY_SCOPE_HINTS = ("账务分类", "成本分类", "收入分类", "费用分类", "支出分类", "自定义分类")
COST_CATEGORY_DELETE_HINTS = ("删除", "删掉", "删")
CROP_TEMPLATE_HINTS = ("作物模板", "模板列表", "有哪些模板", "生长阶段模板")
CROP_CYCLE_LIST_HINTS = (
    "我的茬口",
    "有哪些茬口",
    "茬口列表",
    "种植批次",
    "我的作物",
    "有哪些作物栽种",
    "种了哪些作物",
    "种植哪些作物",
    "地里都种着什么",
)
PLANTING_UNIT_HINTS = ("种植单元", "地块", "大棚", "棚区", "有哪些棚")
PLANTING_UNIT_ENTITY_HINTS = ("种植单元", "地块", "大棚", "棚区", "号棚", "区域")
AMBIGUOUS_PLANTING_UNIT_TARGETS = (
    "这个地块",
    "这个大棚",
    "这个棚区",
    "这个种植单元",
    "该地块",
    "该大棚",
    "该棚区",
    "该种植单元",
)
PLANTING_UNIT_UPDATE_HINTS = ("改", "修改", "更新", "调整", "改成", "设为", "面积")
PLANTING_UNIT_DELETE_HINTS = ("删除", "删掉", "删")
USER_SETTINGS_HINTS = (
    "用户设置",
    "我的设置",
    "默认天气城市",
    "默认城市",
    "天气城市",
    "默认经纬度",
    "经纬度",
    "经度",
    "纬度",
    "助手回复角色",
    "助手角色",
    "回复角色",
    "显示名",
    "昵称",
)
USER_SETTINGS_READ_HINTS = ("什么", "是什么", "当前", "查看", "查询", "查一下", "看看", "多少", "有哪些")
USER_SETTINGS_UPDATE_PATTERNS = (
    r"(?:把|将).{0,16}(?:改成|设为|换成|调整为|更新为)",
    r"(?:设置|修改|调整|更新).{0,16}(?:为|成)",
    r"(?:改成|设为|换成|调整为|更新为).{0,16}",
    r"(?:修改|调整|更新)(?:用户设置|默认天气城市|默认城市|天气城市|默认经纬度|经纬度|经度|纬度|助手回复角色|助手角色|回复角色|显示名|昵称)",
)
WORKER_QUERY_HINTS = (
    "我的工人",
    "工人列表",
    "有哪些工人",
    "看看工人",
    "查询工人",
    "查一下工人",
    "工人有哪些",
)
