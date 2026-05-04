import json
import os
from datetime import datetime, timezone

from utils import generate_data_hash

LANG_LIST = ['en', 'zh-chs', 'zh-cht']

ITEM_BLACKLIST_CATEGORIES = {17, 27, 28, 31, 32, 33, 36, 37, 51, 2150402250, 3109687656, 3301210334}

ITEM_COSMETIC_CATEGORIES = {19, 44, 55, 57, 58}

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
}


def _has_blacklisted_category(item):
    categories = set(item.get('itemCategoryHashes') or [])
    return bool(categories & ITEM_BLACKLIST_CATEGORIES)


def _has_cosmetic_category(item):
    categories = set(item.get('itemCategoryHashes') or [])
    return bool(categories & ITEM_COSMETIC_CATEGORIES)


def _extract_names(definition, lang_list):
    names = {}
    for lang in lang_list:
        name = (definition.get(lang) or {}).get('displayProperties', {}).get('name', '').strip()
        if name:
            names[lang] = name
    return names if len(names) >= 2 else None


def _load_custom_terms():
    path = os.path.join(os.path.dirname(__file__), '..', '..', 'custom_terms.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and 'zh-chs' in data:
            return data.get('zh-chs', {})
        return {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def build(manifest_data, version):
    data_by_bucket = {}

    for def_type, bucket in DEFINITION_BUCKET_MAP.items():
        bucket_data = {}

        primary_lang = LANG_LIST[0]
        primary_defs = manifest_data.get(primary_lang, {}).get(def_type, {})

        for hash_key in primary_defs:
            if def_type == 'DestinyInventoryItemDefinition':
                item = primary_defs[hash_key]
                if _has_blacklisted_category(item):
                    continue
                if _has_cosmetic_category(item):
                    continue

            names = {}
            for lang in LANG_LIST:
                lang_defs = manifest_data.get(lang, {}).get(def_type, {})
                entry = lang_defs.get(hash_key)
                if not entry:
                    continue
                name = entry.get('displayProperties', {}).get('name', '').strip()
                if name:
                    names[lang] = name

            if len(names) >= 2:
                bucket_data[hash_key] = names

        data_by_bucket[bucket] = bucket_data

    custom_terms = _load_custom_terms()
    custom_bucket = {}
    for idx, (en, zh_chs) in enumerate(custom_terms.items(), start=1):
        entry = {'en': en, 'zh-chs': zh_chs}
        custom_bucket[str(idx)] = entry

    data_by_bucket['custom'] = custom_bucket

    metadata = {
        'version': version,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'data_hash': generate_data_hash(data_by_bucket),
        'source': 'Bungie Destiny 2 Manifest',
        'languages': LANG_LIST,
        'definition_types': list(DEFINITION_BUCKET_MAP.keys()),
    }

    return {'metadata': metadata, 'data': data_by_bucket}
