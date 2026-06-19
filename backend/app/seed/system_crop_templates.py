from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.models.crop import CropTemplate, GrowthStage

SYSTEM_CROP_TEMPLATES: list[dict[str, Any]] = [
    {
        "category": "粮食",
        "name": "水稻",
        "variety": "通用移栽稻",
        "stages": [
            {
                "name": "育秧期",
                "duration_days": 25,
                "order_index": 0,
                "key_tasks": "浸种催芽，秧田管理，防治苗期病害",
            },
            {
                "name": "返青分蘖期",
                "duration_days": 35,
                "order_index": 1,
                "key_tasks": "浅水返青，追施分蘖肥，控草除草",
            },
            {
                "name": "拔节孕穗期",
                "duration_days": 30,
                "order_index": 2,
                "key_tasks": "水肥调控，晒田控蘖，监测纹枯病",
            },
            {
                "name": "抽穗灌浆期",
                "duration_days": 35,
                "order_index": 3,
                "key_tasks": "保持浅水，防治稻飞虱，适期收获",
            },
        ],
    },
    {
        "category": "粮食",
        "name": "小麦",
        "variety": "冬小麦通用型",
        "stages": [
            {
                "name": "播种出苗期",
                "duration_days": 15,
                "order_index": 0,
                "key_tasks": "整地施底肥，适墒播种，查苗补缺",
            },
            {
                "name": "越冬返青期",
                "duration_days": 100,
                "order_index": 1,
                "key_tasks": "镇压保墒，返青水肥，防冻害",
            },
            {
                "name": "拔节孕穗期",
                "duration_days": 35,
                "order_index": 2,
                "key_tasks": "追施拔节肥，控旺防倒，监测蚜虫",
            },
            {
                "name": "抽穗成熟期",
                "duration_days": 45,
                "order_index": 3,
                "key_tasks": "防治赤霉病，灌浆保墒，适期机收",
            },
        ],
    },
    {
        "category": "粮食",
        "name": "玉米",
        "variety": "春玉米通用型",
        "stages": [
            {
                "name": "播种出苗期",
                "duration_days": 10,
                "order_index": 0,
                "key_tasks": "精量播种，覆土镇压，查苗补苗",
            },
            {
                "name": "苗期",
                "duration_days": 25,
                "order_index": 1,
                "key_tasks": "中耕除草，间苗定苗，防治地老虎",
            },
            {
                "name": "拔节抽雄期",
                "duration_days": 45,
                "order_index": 2,
                "key_tasks": "追施攻秆肥，培土防倒，监测玉米螟",
            },
            {
                "name": "灌浆成熟期",
                "duration_days": 40,
                "order_index": 3,
                "key_tasks": "保叶护根，防旱排涝，籽粒成熟后收获",
            },
        ],
    },
    {
        "category": "油料豆类",
        "name": "大豆",
        "variety": "夏大豆通用型",
        "stages": [
            {
                "name": "播种出苗期",
                "duration_days": 10,
                "order_index": 0,
                "key_tasks": "精细整地，接种根瘤菌，适墒播种",
            },
            {
                "name": "苗期",
                "duration_days": 25,
                "order_index": 1,
                "key_tasks": "间苗定苗，中耕除草，防治蚜虫",
            },
            {
                "name": "开花结荚期",
                "duration_days": 35,
                "order_index": 2,
                "key_tasks": "保证水分，叶面追肥，防治食心虫",
            },
            {
                "name": "鼓粒成熟期",
                "duration_days": 30,
                "order_index": 3,
                "key_tasks": "防早衰，控水防倒，荚黄叶落后收获",
            },
        ],
    },
    {
        "category": "蔬菜",
        "name": "番茄",
        "variety": "设施番茄通用型",
        "stages": [
            {
                "name": "育苗期",
                "duration_days": 35,
                "order_index": 0,
                "key_tasks": "穴盘育苗，控温控湿，炼苗壮苗",
            },
            {
                "name": "定植缓苗期",
                "duration_days": 12,
                "order_index": 1,
                "key_tasks": "施足基肥，定植浇缓苗水，查苗补苗",
            },
            {
                "name": "开花坐果期",
                "duration_days": 35,
                "order_index": 2,
                "key_tasks": "整枝吊蔓，授粉保果，控制旺长",
            },
            {
                "name": "采收期",
                "duration_days": 70,
                "order_index": 3,
                "key_tasks": "分批采收，水肥一体化，防治灰霉病",
            },
        ],
    },
    {
        "category": "蔬菜",
        "name": "辣椒",
        "variety": "设施辣椒通用型",
        "stages": [
            {
                "name": "育苗期",
                "duration_days": 40,
                "order_index": 0,
                "key_tasks": "温汤浸种，育苗控温，预防猝倒病",
            },
            {
                "name": "定植缓苗期",
                "duration_days": 12,
                "order_index": 1,
                "key_tasks": "覆膜定植，浇缓苗水，促根壮苗",
            },
            {
                "name": "开花结果期",
                "duration_days": 45,
                "order_index": 2,
                "key_tasks": "控氮增钾，整枝打杈，防治蓟马",
            },
            {
                "name": "连续采收期",
                "duration_days": 60,
                "order_index": 3,
                "key_tasks": "分批采收，追肥补钾，防治疫病",
            },
        ],
    },
    {
        "category": "蔬菜",
        "name": "黄瓜",
        "variety": "设施黄瓜通用型",
        "stages": [
            {
                "name": "育苗期",
                "duration_days": 25,
                "order_index": 0,
                "key_tasks": "嫁接或穴盘育苗，控温保湿，炼苗",
            },
            {
                "name": "定植伸蔓期",
                "duration_days": 20,
                "order_index": 1,
                "key_tasks": "吊蔓引蔓，浇缓苗水，促根控旺",
            },
            {
                "name": "结瓜期",
                "duration_days": 55,
                "order_index": 2,
                "key_tasks": "水肥一体化，疏瓜整枝，防治霜霉病",
            },
            {
                "name": "采收更新期",
                "duration_days": 35,
                "order_index": 3,
                "key_tasks": "及时采收，落蔓更新，清除病叶",
            },
        ],
    },
    {
        "category": "水果",
        "name": "西瓜",
        "variety": "8424通用型",
        "stages": [
            {
                "name": "育苗期",
                "duration_days": 30,
                "order_index": 0,
                "key_tasks": "浸种催芽，控温育苗，炼苗",
            },
            {
                "name": "定植伸蔓期",
                "duration_days": 25,
                "order_index": 1,
                "key_tasks": "定植浇水，整枝压蔓，防低温",
            },
            {
                "name": "开花坐瓜期",
                "duration_days": 20,
                "order_index": 2,
                "key_tasks": "人工授粉，选留果，控制氮肥",
            },
            {
                "name": "膨瓜成熟期",
                "duration_days": 35,
                "order_index": 3,
                "key_tasks": "追施膨瓜肥，控水增甜，适熟采收",
            },
        ],
    },
    {
        "category": "水果",
        "name": "草莓",
        "variety": "设施草莓通用型",
        "stages": [
            {
                "name": "定植缓苗期",
                "duration_days": 20,
                "order_index": 0,
                "key_tasks": "高垄定植，遮阴缓苗，去除老叶",
            },
            {
                "name": "营养生长期",
                "duration_days": 35,
                "order_index": 1,
                "key_tasks": "控温控湿，促根壮苗，防治螨虫",
            },
            {
                "name": "开花结果期",
                "duration_days": 45,
                "order_index": 2,
                "key_tasks": "放蜂授粉，疏花疏果，补钙防畸形",
            },
            {
                "name": "连续采收期",
                "duration_days": 75,
                "order_index": 3,
                "key_tasks": "分级采收，病果清理，水肥调控",
            },
        ],
    },
    {
        "category": "蔬菜",
        "name": "生菜",
        "variety": "叶用生菜通用型",
        "stages": [
            {
                "name": "播种育苗期",
                "duration_days": 18,
                "order_index": 0,
                "key_tasks": "低温催芽，穴盘育苗，保持基质湿润",
            },
            {
                "name": "定植缓苗期",
                "duration_days": 7,
                "order_index": 1,
                "key_tasks": "浅栽定植，浇足定根水，遮阴缓苗",
            },
            {
                "name": "莲座生长期",
                "duration_days": 25,
                "order_index": 2,
                "key_tasks": "薄肥勤施，保持土壤湿润，防治软腐病",
            },
            {
                "name": "采收期",
                "duration_days": 5,
                "order_index": 3,
                "key_tasks": "清晨采收，去除老叶，预冷保鲜",
            },
        ],
    },
]


def seed_system_crop_templates(db: Session) -> int:
    """写入系统作物模板初稿，返回新增模板数量。"""
    added_count = 0
    for template_data in SYSTEM_CROP_TEMPLATES:
        if _system_template_exists(db, template_data):
            continue
        template = CropTemplate(
            farm_id=None,
            category=template_data["category"],
            name=template_data["name"],
            variety=template_data["variety"],
        )
        db.add(template)
        db.flush()
        for stage_data in template_data["stages"]:
            db.add(
                GrowthStage(
                    crop_template_id=template.id,
                    name=stage_data["name"],
                    duration_days=stage_data["duration_days"],
                    order_index=stage_data["order_index"],
                    key_tasks=stage_data["key_tasks"],
                )
            )
        added_count += 1

    if added_count:
        db.commit()
    return added_count


def _system_template_exists(db: Session, template_data: Mapping[str, Any]) -> bool:
    query = db.query(CropTemplate).filter(
        CropTemplate.farm_id.is_(None),
        CropTemplate.name == template_data["name"],
    )
    if template_data["variety"] is None:
        query = query.filter(CropTemplate.variety.is_(None))
    else:
        query = query.filter(CropTemplate.variety == template_data["variety"])
    return db.query(query.exists()).scalar()


def iter_system_template_keys() -> Iterable[tuple[str, str | None]]:
    """返回 seed 系统模板的 name/variety 键，用于数据迁移回滚。"""
    for template_data in SYSTEM_CROP_TEMPLATES:
        yield template_data["name"], template_data["variety"]
