"""离线把 term-map.json 补成新结构，不联网。

    python scripts/patch_term_map.py

做四件事：
  1. 按物品分类把装饰品（染色器/机灵/飞船/鸟卫/幻饰…）从 items 拆到 cosmetics 桶
  2. 从 manifest_raw/ 补 records / npcs / factions / milestones / seasons 五个桶
  3. 依 custom_terms.json 重建 custom 与 partials 桶
  4. 应用 _exclude、刷新 data_hash

manifest_raw/ 只有 en 与 zh-chs，新增的五个桶因此暂缺 zh-cht；跑一次
`python scripts/fetch_manifest.py` 联网重建后即补齐，届时本脚本可删。
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from builders import term_map_builder
from utils import generate_data_hash

REPO = Path(__file__).resolve().parents[1]
TERM_MAP = REPO / 'term-map.json'
RAW = REPO / 'manifest_raw'

# 只有 itemCategoryHashes 用得上，Lite 表够用且比全表小 3 倍
ITEM_CATEGORY_SOURCE = 'DestinyInventoryItemLiteDefinition'

NEW_BUCKETS = {
    'records': 'DestinyRecordDefinition',
    'npcs': 'DestinyVendorDefinition',
    'factions': 'DestinyFactionDefinition',
    'milestones': 'DestinyMilestoneDefinition',
    'seasons': 'DestinySeasonDefinition',
}

PATCH_LANGS = ['en', 'zh-chs']


def load_raw(lang, def_type):
    path = RAW / lang / f'{def_type}.json'
    if not path.exists():
        raise SystemExit(f'缺少 {path}，先跑 download_all_manifest.py')
    return json.loads(path.read_text(encoding='utf-8'))


def split_cosmetics(data):
    """按 itemCategoryHashes 把 items 里的装饰品挪进 cosmetics。

    源是 items + cosmetics 的并集，重跑本脚本不会把已拆出去的条目丢掉。
    """
    lite = load_raw('en', ITEM_CATEGORY_SOURCE)
    categories = {h: (d.get('itemCategoryHashes') or []) for h, d in lite.items()}
    del lite

    source = {**data.get('items', {}), **data.get(term_map_builder.COSMETIC_BUCKET, {})}
    items, cosmetics = {}, {}
    unknown = 0
    for hash_key, entry in source.items():
        if hash_key not in categories:
            unknown += 1
            items[hash_key] = entry
            continue
        dest = term_map_builder.classify_item({'itemCategoryHashes': categories[hash_key]})
        if dest is None:
            continue
        (cosmetics if dest == term_map_builder.COSMETIC_BUCKET else items)[hash_key] = entry

    print(f'items {len(source)} → items {len(items)} + cosmetics {len(cosmetics)}（Lite 表未收录 {unknown} 条，保留）')
    return items, cosmetics


def build_new_bucket(bucket, def_type):
    """从 manifest_raw 的 en + zh-chs 建一个新桶（暂无 zh-cht）"""
    manifest_data = {lang: {def_type: load_raw(lang, def_type)} for lang in PATCH_LANGS}
    primary = manifest_data['en'][def_type]

    keep = term_map_builder.BUCKET_FILTERS.get(bucket)
    result = {}
    for hash_key in primary:
        if keep and not keep(primary[hash_key]):
            continue
        names = term_map_builder.extract_names(manifest_data, def_type, hash_key)
        if names:
            result[hash_key] = names

    print(f'{bucket:<12} {len(result)} 条（源表 {len(primary)} 条）')
    return result


def main():
    term_map = json.loads(TERM_MAP.read_text(encoding='utf-8'))
    old = term_map['data']

    items, cosmetics = split_cosmetics(old)

    data = {'items': items, term_map_builder.COSMETIC_BUCKET: cosmetics}
    for def_type, bucket in term_map_builder.DEFINITION_BUCKET_MAP.items():
        if bucket in data:
            continue
        data[bucket] = build_new_bucket(bucket, def_type) if bucket in NEW_BUCKETS else old.get(bucket, {})

    custom_data = term_map_builder.load_custom_terms()
    data['custom'] = term_map_builder.build_custom_bucket(custom_data)
    data['partials'] = term_map_builder.build_partials_bucket(custom_data)
    print(f'custom {len(data["custom"])} 条，partials {len(data["partials"])} 条')

    exclude = set(custom_data.get('_exclude') or ())
    dropped = [(b, h) for b, entries in data.items() for h in entries if h in exclude]
    for bucket, hash_key in dropped:
        del data[bucket][hash_key]
        print(f'_exclude 移除 {bucket}/{hash_key}')

    term_map['data'] = data
    term_map['metadata']['timestamp'] = datetime.now(timezone.utc).isoformat()
    term_map['metadata']['data_hash'] = generate_data_hash(data)
    term_map['metadata']['definition_types'] = list(term_map_builder.DEFINITION_BUCKET_MAP)

    TERM_MAP.write_text(json.dumps(term_map, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    total = sum(len(v) for v in data.values())
    print(f'\n已写入 term-map.json：{len(data)} 个桶，{total} 条')
    print('新增的 records/npcs/factions/milestones/seasons 暂无 zh-cht，联网重建后补齐')


if __name__ == '__main__':
    main()
