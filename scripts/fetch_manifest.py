import json
import os
import time
import sys
from datetime import datetime, timezone

from utils import validate_api_key, get_manifest
from builders import term_map_builder, items_full_builder

BUNGIE_API_KEY = os.getenv('BUNGIE_API_KEY')
LANG_LIST = ['en', 'zh-chs', 'zh-cht']

ALL_DEFINITION_TYPES = [
    'DestinyInventoryItemDefinition',
    'DestinyActivityDefinition',
    'DestinyActivityTypeDefinition',
    'DestinyActivityModeDefinition',
    'DestinyActivityModifierDefinition',
    'DestinyDestinationDefinition',
    'DestinyStatDefinition',
    'DestinySandboxPerkDefinition',
    'DestinyItemCategoryDefinition',
    'DestinyDamageTypeDefinition',
    'DestinyClassDefinition',
]

DOWNLOAD_DELAY = 1.5


def download_definitions(manifest, definition_types, lang_list):
    manifest_data = {}
    total = len(definition_types) * len(lang_list)
    done = 0

    for def_type in definition_types:
        for lang in lang_list:
            done += 1
            paths = manifest['Response']['jsonWorldComponentContentPaths'].get(lang, {})
            path = paths.get(def_type)

            if not path:
                print(f'  [{done}/{total}] 跳过 {def_type} ({lang}): 未找到路径')
                continue

            url = f'https://www.bungie.net{path}'
            print(f'  [{done}/{total}] 下载 {def_type} ({lang})...')

            try:
                import requests
                response = requests.get(url, headers={'X-API-Key': BUNGIE_API_KEY}, timeout=60)
                response.raise_for_status()
                data = response.json()

                if lang not in manifest_data:
                    manifest_data[lang] = {}
                manifest_data[lang][def_type] = data

                print(f'         成功: {len(data)} 条')
            except Exception as e:
                print(f'         失败: {e}', file=sys.stderr)

            time.sleep(DOWNLOAD_DELAY)

    return manifest_data


def save_json(data, filename):
    path = os.path.join(os.path.dirname(__file__), '..', filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    count = len(data.get('data', {}))
    print(f'已保存 {filename} ({count} 个桶)' if isinstance(data.get('data'), dict) else f'已保存 {filename}')


def main():
    start_time = datetime.now(timezone.utc)

    validate_api_key(BUNGIE_API_KEY)

    print('正在获取 Manifest...')
    manifest = get_manifest(BUNGIE_API_KEY)
    version = manifest['Response']['version']
    print(f'Manifest 版本: {version}')

    print(f'\n正在下载 {len(ALL_DEFINITION_TYPES)} 种定义 × {len(LANG_LIST)} 种语言...')
    manifest_data = download_definitions(manifest, ALL_DEFINITION_TYPES, LANG_LIST)

    print('\n正在构建 term-map.json...')
    term_map = term_map_builder.build(manifest_data, version)
    save_json(term_map, 'term-map.json')

    print('\n正在构建 items-full.json...')
    items_full = items_full_builder.build(manifest_data, version)
    save_json(items_full, 'items-full.json')

    duration = datetime.now(timezone.utc) - start_time
    print(f'\n完成! 总耗时: {duration}')


if __name__ == '__main__':
    main()
