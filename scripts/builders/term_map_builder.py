import json
import os
from datetime import datetime, timezone

from utils import generate_data_hash

LANG_LIST = ['en', 'zh-chs', 'zh-cht']

# 废弃/未命名分类 + 图纸/礼包/测试假物品/商城包装
ITEM_BLACKLIST_CATEGORIES = {
    17,
    27,
    28,
    31,
    32,
    33,
    36,
    37,
    51,
    2150402250,
    3109687656,
    3301210334,
}

# 徽章/表情/面具/光环/战团旗：名字多为日常词，直接丢弃
ITEM_DROP_CATEGORIES = {19, 44, 55, 57, 58}

# 染色器/机灵/飞船/鸟卫/机灵幻影/传送特效/终结动作/护甲幻饰/武器幻饰
# 名字同样是 Help/Soon/Trust 这类日常词，但有翻译价值，分流到 cosmetics 桶由使用方自行开关
ITEM_COSMETIC_CATEGORIES = {
    39,
    41,
    42,
    43,
    1404791674,
    208981632,
    1112488720,
    1742617626,
    3124752623,
}

DEFINITION_BUCKET_MAP = {
    'DestinyInventoryItemDefinition': 'items',
    'DestinyActivityDefinition': 'activities',
    'DestinyActivityTypeDefinition': 'activity_types',
    'DestinyActivityModeDefinition': 'activity_modes',
    'DestinyActivityModifierDefinition': 'modifiers',
    'DestinyDestinationDefinition': 'destinations',
    'DestinyStatDefinition': 'stats',
    'DestinySandboxPerkDefinition': 'perks',
    'DestinyItemCategoryDefinition': 'categories',
    'DestinyDamageTypeDefinition': 'damage_types',
    'DestinyClassDefinition': 'classes',
    'DestinyRecordDefinition': 'records',
    'DestinyVendorDefinition': 'npcs',
    'DestinyFactionDefinition': 'factions',
    'DestinyMilestoneDefinition': 'milestones',
    'DestinySeasonDefinition': 'seasons',
}

COSMETIC_BUCKET = 'cosmetics'

# 商人表里绝大多数条目是货架分类（"Distorted Engram" 之类）而非 NPC，带 subtitle 的才是真人。
# 与 build_dataset.py 的 build_npcs() 同一条判据。
BUCKET_FILTERS = {
    'npcs': lambda d: bool(d.get('displayProperties', {}).get('subtitle', '').strip()),
}


def classify_item(item):
    """物品分流：None=丢弃，COSMETIC_BUCKET=装饰品桶，'items'=正常桶"""
    categories = set(item.get('itemCategoryHashes') or [])
    if categories & ITEM_BLACKLIST_CATEGORIES or categories & ITEM_DROP_CATEGORIES:
        return None
    if categories & ITEM_COSMETIC_CATEGORIES:
        return COSMETIC_BUCKET
    return 'items'


def extract_names(manifest_data, def_type, hash_key):
    """取各语言的 displayProperties.name，少于 2 种语言的条目视为无效"""
    names = {}
    for lang in LANG_LIST:
        entry = manifest_data.get(lang, {}).get(def_type, {}).get(hash_key)
        if not entry:
            continue
        name = entry.get('displayProperties', {}).get('name', '').strip()
        if name:
            names[lang] = name
    return names if len(names) >= 2 else None


def load_custom_terms():
    """整份 custom_terms.json；缺失或损坏时退回空结构（各桶为空，不影响 manifest 部分）"""
    path = os.path.join(os.path.dirname(__file__), '..', '..', 'custom_terms.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _pair_bucket(chs, cht):
    bucket = {}
    for idx, (en, zh_chs) in enumerate(chs.items(), start=1):
        entry = {'en': en, 'zh-chs': zh_chs}
        if cht.get(en):
            entry['zh-cht'] = cht[en]
        bucket[str(idx)] = entry
    return bucket


def build_custom_bucket(custom_data):
    """顶层 zh-chs / zh-cht → data.custom，id 按 zh-chs 插入顺序 1..N"""
    return _pair_bucket(custom_data.get('zh-chs') or {}, custom_data.get('zh-cht') or {})


def build_partials_bucket(custom_data):
    """partials 区 → data.partials（框架/碎片短词，使用方默认关闭）"""
    partials = custom_data.get('partials') or {}
    return _pair_bucket(partials.get('zh-chs') or {}, partials.get('zh-cht') or {})


def build(manifest_data, version):
    custom_data = load_custom_terms()
    # ponytail: _exclude 是扁平 hash 列表而非 bucket→hash 映射，manifest 各表间 hash 实际不撞
    exclude = set(custom_data.get('_exclude') or ())
    data_by_bucket = {}
    cosmetic_data = {}

    for def_type, bucket in DEFINITION_BUCKET_MAP.items():
        bucket_data = {}
        primary_defs = manifest_data.get(LANG_LIST[0], {}).get(def_type, {})
        keep = BUCKET_FILTERS.get(bucket)

        for hash_key in primary_defs:
            if hash_key in exclude:
                continue
            if keep and not keep(primary_defs[hash_key]):
                continue

            target = bucket_data
            if def_type == 'DestinyInventoryItemDefinition':
                dest = classify_item(primary_defs[hash_key])
                if dest is None:
                    continue
                if dest == COSMETIC_BUCKET:
                    target = cosmetic_data

            names = extract_names(manifest_data, def_type, hash_key)
            if names:
                target[hash_key] = names

        data_by_bucket[bucket] = bucket_data
        if def_type == 'DestinyInventoryItemDefinition':
            data_by_bucket[COSMETIC_BUCKET] = cosmetic_data

    data_by_bucket['custom'] = build_custom_bucket(custom_data)
    data_by_bucket['partials'] = build_partials_bucket(custom_data)

    metadata = {
        'version': version,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'data_hash': generate_data_hash(data_by_bucket),
        'source': 'Bungie Destiny 2 Manifest',
        'languages': LANG_LIST,
        'definition_types': list(DEFINITION_BUCKET_MAP.keys()),
    }

    return {'metadata': metadata, 'data': data_by_bucket}
