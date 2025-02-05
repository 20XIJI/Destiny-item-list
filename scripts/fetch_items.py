import requests
import json
import os
import hashlib
from datetime import datetime, UTC

BUNGIE_API_KEY = os.getenv('BUNGIE_API_KEY')
LANG_LIST = ['zh-chs', 'en']
MANIFEST_URL = 'https://www.bungie.net/Platform/Destiny2/Manifest/'

def get_manifest_version():
    """获取当前Manifest版本"""
    response = requests.get(MANIFEST_URL, headers={'X-API-Key': BUNGIE_API_KEY})
    response.raise_for_status()
    return response.json()['Response']['version']

def fetch_item_definitions(lang):
    """获取指定语言的物品定义"""
    manifest = requests.get(MANIFEST_URL, headers={'X-API-Key': BUNGIE_API_KEY}).json()
    item_path = manifest['Response']['jsonWorldComponentContentPaths'][lang]['DestinyInventoryItemLiteDefinition']
    return requests.get(f'https://www.bungie.net{item_path}', headers={'X-API-Key': BUNGIE_API_KEY}).json()

def generate_item_hash(data):
    """生成数据哈希用于检测变更"""
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

def main():
    # 获取当前版本
    current_version = get_manifest_version()
    print(f"Current Manifest Version: {current_version}")
    
    # 获取各语言数据
    items = {}
    for lang in LANG_LIST:
        items[lang] = fetch_item_definitions(lang)
        print(f"Fetched {len(items[lang])} items for {lang}")

    # 合并数据
    combined = {}
    for item_id in items[LANG_LIST[0]]:
        item = items[LANG_LIST[0]][item_id]
        if item.get('itemCategoryHashes') and item.get('displayProperties', {}).get('name'):
            combined[item_id] = {
                lang: items[lang][item_id]['displayProperties']['name']
                for lang in LANG_LIST
            }

    # 生成元数据
    metadata = {
        "version": current_version,
        "timestamp": datetime.now(UTC).isoformat(),
        "item_count": len(combined),
        "data_hash": generate_item_hash(combined)
    }

    # 保存文件
    output = {
        "metadata": metadata,
        "data": combined
    }
    
    with open('item-list-8-2-0.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()