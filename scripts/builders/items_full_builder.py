from datetime import datetime, timezone

from utils import generate_data_hash

LANG_LIST = ['en', 'zh-chs', 'zh-cht']

ITEM_BLACKLIST_CATEGORIES = {17, 27, 28, 31, 32, 33, 36, 37, 51, 2150402250, 3109687656, 3301210334}

BUNGIE_BASE = 'https://www.bungie.net'


def _has_blacklisted_category(item):
    categories = set(item.get('itemCategoryHashes') or [])
    return bool(categories & ITEM_BLACKLIST_CATEGORIES)


def build(manifest_data, version):
    primary_defs = manifest_data.get('en', {}).get('DestinyInventoryItemDefinition', {})
    items = {}

    for hash_key, en_item in primary_defs.items():
        if _has_blacklisted_category(en_item):
            continue

        if not en_item.get('displayProperties', {}).get('name', '').strip():
            continue

        entry = {}

        for lang in LANG_LIST:
            lang_defs = manifest_data.get(lang, {}).get('DestinyInventoryItemDefinition', {})
            item = lang_defs.get(hash_key)
            if not item:
                continue

            dp = item.get('displayProperties', {})
            name = dp.get('name', '').strip()
            desc = dp.get('description', '').strip()
            icon = dp.get('icon', '')

            if lang == 'en':
                entry['en'] = name
                entry['desc_en'] = desc
            elif lang == 'zh-chs':
                entry['zh-chs'] = name
                entry['desc_zh-chs'] = desc
            elif lang == 'zh-cht':
                entry['zh-cht'] = name
                entry['desc_zh-cht'] = desc

            if icon and 'icon' not in entry:
                entry['icon'] = f'{BUNGIE_BASE}{icon}' if icon.startswith('/') else icon

        if not entry.get('en') or not entry.get('zh-chs'):
            continue

        entry['tierType'] = en_item.get('tierType', 0)
        entry['itemType'] = en_item.get('itemType', 0)
        entry['itemSubType'] = en_item.get('itemSubType', 0)
        entry['classType'] = en_item.get('classType', 3)

        items[hash_key] = entry

    metadata = {
        'version': version,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'item_count': len(items),
        'data_hash': generate_data_hash(items),
        'source': 'Bungie Destiny 2 Manifest',
        'languages': LANG_LIST,
        'definition_type': 'DestinyInventoryItemDefinition',
    }

    return {'metadata': metadata, 'data': items}
