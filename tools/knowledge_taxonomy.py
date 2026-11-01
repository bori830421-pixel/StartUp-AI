#!/usr/bin/env python3
"""检索沉淀的分类层：城市层级、品类号、路径解析。

从 knowledge_sink.py 拆出（决策 0026 的 500 行停手线）。这里只有「归类」——
把城市落到层级、把品类号归一、算出该写哪个文件，不含任何读写与渲染。
"""
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGIONS = os.path.join(REPO, "local-knowledge", "regions")

# 城市层级：默认归类，不是硬约束。差异大的城市用 --solo 单独成文件。
TIERS = {
    "一线": ["北京", "上海", "广州", "深圳"],
    "新一线": ["成都", "杭州", "重庆", "西安", "苏州", "武汉", "南京",
               "天津", "郑州", "长沙", "东莞", "青岛", "沈阳", "宁波", "昆明"],
    "二线": ["合肥", "佛山", "福州", "厦门", "哈尔滨", "济南", "温州", "大连",
             "无锡", "石家庄", "泉州", "南宁", "金华", "贵阳", "常州", "长春",
             "南昌", "南通", "嘉兴", "徐州", "惠州", "太原", "烟台", "临沂",
             "保定", "台州", "绍兴", "珠海", "潍坊", "海口"],
    "三线及以下": [],
}

TIER_NOTE = {
    "一线": "北上广深，租金与工资最高，同一组内差异仍大",
    "新一线": "省会与强地级市，样本差异中等",
    "二线": "普通地级市，样本差异较小",
    "三线及以下": "县级市与县域，公开挂牌样本少，多数要靠实地询价",
}

CATEGORIES = {
    "01": "餐饮食品", "02": "零售卖货·线下", "03": "电商与线上卖货",
    "04": "居民生活服务", "05": "出行与配送", "06": "技能接单与专业服务",
    "07": "内容与流量", "08": "加盟连锁", "09": "教育与文体娱",
    "10": "涉农与食品加工", "11": "租赁与中介",
}


def _known_cities() -> set:
    return {c for cities in TIERS.values() for c in cities}


def normalize_category(category: str) -> str:
    """品类号归一：接受 01 / 1 / 餐饮食品，统一成两位号。不认识的抛 ValueError。

    不校验会让「--category 餐饮」和「--category 01」各建一节，同一品类散成两份，
    下次按 01 找记录就漏掉另一半。
    """
    raw = category.strip()
    if raw.isdigit():
        num = raw.zfill(2)
        if num in CATEGORIES:
            return num
    for num, name in CATEGORIES.items():
        if raw in (name, name.replace("·", "").replace("与", "")):
            return num
    raise ValueError(f"未知品类 {category!r}，可用：{', '.join(sorted(CATEGORIES))}")


def normalize_city(city: str) -> str:
    """城市名归一：去掉「市/区/县/镇」后缀，区县名归到所属城市。

    深圳宝安 → 深圳，深圳市 → 深圳。不归一会把同一个城市写成两三个子节，
    而且区县名匹配不到层级表，会被错判成三线。
    """
    name = city.strip()
    for suffix in ("市", "区", "县", "镇"):
        if name.endswith(suffix) and len(name) > len(suffix):
            name = name[: -len(suffix)]
    known = _known_cities()
    if name in known:
        return name
    hits = [c for c in known if name.startswith(c)]
    return max(hits, key=len) if hits else name


def is_known_city(city: str) -> bool:
    return normalize_city(city) in _known_cities()


def tier_of(city: str) -> str:
    """城市名 → 层级。匹配不到落「三线及以下」，调用方可用 is_known_city 提示。"""
    name = normalize_city(city)
    for tier, cities in TIERS.items():
        if name in cities:
            return tier
    return "三线及以下"


def tier_path(tier: str, regions: str | None = None) -> str:
    return os.path.join(regions or REGIONS, f"{tier}.md")


def solo_path(city: str, regions: str | None = None) -> str:
    """城市单独成文件时的路径。用子目录避免和层级文件混在一起。"""
    return os.path.join(regions or REGIONS, "城市", f"{normalize_city(city)}.md")


def is_solo(city: str, regions: str | None = None) -> bool:
    return os.path.exists(solo_path(city, regions))


def resolve_path(city: str, solo: bool | None = None,
                 regions: str | None = None) -> tuple:
    """城市 → (文件路径, 是否单独文件)。

    solo=None 时按现状：已单独成文件就继续用它，否则落层级文件。
    这样重复写入不会因为漏传 --solo 就分叉成两份。
    """
    if solo is True:
        return solo_path(city, regions), True
    if solo is False:
        return tier_path(tier_of(city), regions), False
    if is_solo(city, regions):
        return solo_path(city, regions), True
    return tier_path(tier_of(city), regions), False
