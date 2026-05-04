import json
import os
import requests
from datetime import datetime, timezone

from utils import validate_api_key, get_manifest, generate_data_hash

BUNGIE_API_KEY = os.getenv('BUNGIE_API_KEY')
LANG_LIST = ['zh-chs', 'en']


def fetch_item_definitions(manifest, lang):
    item_path = manifest['Response']['jsonWorldComponentContentPaths'][lang]['DestinyInventoryItemLiteDefinition']
    return requests.get(f'https://www.bungie.net{item_path}', headers={'X-API-Key': BUNGIE_API_KEY}).json()


def main():
    validate_api_key(BUNGIE_API_KEY)

    manifest = get_manifest(BUNGIE_API_KEY)
    current_version = manifest['Response']['version']
    print(f"Current Manifest Version: {current_version}")

    items = {}
    for lang in LANG_LIST:
        items[lang] = fetch_item_definitions(manifest, lang)
        print(f"Fetched {len(items[lang])} items for {lang}")

    combined = {}
    for item_id in items[LANG_LIST[0]]:
        item = items[LANG_LIST[0]][item_id]
        if item.get('itemCategoryHashes') and item.get('displayProperties', {}).get('name'):
            combined[item_id] = {
                lang: items[lang][item_id]['displayProperties']['name']
                for lang in LANG_LIST
            }

    metadata = {
        "version": current_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "item_count": len(combined),
        "data_hash": generate_data_hash(combined)
    }

    output = {
        "metadata": metadata,
        "data": combined
    }

    with open('item-list.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
